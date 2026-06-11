"""Quota-aware live polling: fixtures?live=all → Postgres → WebSocket fanout.

Only runs when LIVE_DATA_MODE=api. Demo mode uses matchday_demo.py instead.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session
from app.models import ApiCache, Match, MatchStatus
from app.services.api_football import ApiFootballClient, QuotaHalted
from app.services.matchday_live import (
    apply_fixture_snapshot,
    build_match_maps,
    link_api_fixture_ids,
    merge_api_events,
)
from app.services.openfootball import OFFICIAL_EXTERNAL_PREFIX

logger = logging.getLogger(__name__)

INTERVAL_IDLE = 120
INTERVAL_PRE_KICKOFF = 180
INTERVAL_LIVE_DEFAULT = 300
INTERVAL_LIVE_BURST = 90

PRE_KICKOFF_BUFFER = timedelta(minutes=15)
POST_MATCH_BUFFER = timedelta(minutes=20)
MATCH_DURATION = timedelta(hours=2, minutes=15)
BURST_DURATION = timedelta(minutes=5)

STANDINGS_CACHE_KEY = "api_football:standings_synced"


@dataclass
class PollerState:
    accelerated_until: datetime | None = None
    last_poll_at: datetime | None = None
    pending_event_fetch: dict[int, int] = field(default_factory=dict)


_state = PollerState()


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def trigger_burst() -> None:
    _state.accelerated_until = datetime.now(timezone.utc) + BURST_DURATION


def _in_burst() -> bool:
    if _state.accelerated_until is None:
        return False
    return datetime.now(timezone.utc) < _state.accelerated_until


@dataclass
class PollingWindow:
    active: bool
    seconds_until_active: float = INTERVAL_IDLE
    in_live_window: bool = False


async def compute_polling_window(db: AsyncSession) -> PollingWindow:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Match)
        .where(
            Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"),
            or_(
                Match.status == MatchStatus.LIVE,
                Match.status == MatchStatus.SCHEDULED,
            ),
        )
        .order_by(Match.kickoff_at)
    )
    rows = result.scalars().all()

    if any(m.status == MatchStatus.LIVE for m in rows):
        return PollingWindow(active=True, in_live_window=True)

    upcoming = [
        m
        for m in rows
        if m.status == MatchStatus.SCHEDULED and _aware(m.kickoff_at) is not None
    ]
    if not upcoming:
        return PollingWindow(active=False, seconds_until_active=INTERVAL_IDLE)

    for m in upcoming:
        kickoff = _aware(m.kickoff_at)
        assert kickoff is not None
        window_start = kickoff - PRE_KICKOFF_BUFFER
        window_end = kickoff + MATCH_DURATION + POST_MATCH_BUFFER
        if window_start <= now <= window_end:
            return PollingWindow(active=True, in_live_window=False)

    next_kick = _aware(upcoming[0].kickoff_at)
    if next_kick and next_kick > now:
        wait = (next_kick - PRE_KICKOFF_BUFFER - now).total_seconds()
        return PollingWindow(active=False, seconds_until_active=max(60, min(wait, 600)))

    return PollingWindow(active=False, seconds_until_active=INTERVAL_IDLE)


def next_poll_interval(window: PollingWindow) -> float:
    if _in_burst():
        return INTERVAL_LIVE_BURST
    if window.in_live_window:
        return INTERVAL_LIVE_DEFAULT
    if window.active:
        return INTERVAL_PRE_KICKOFF
    return window.seconds_until_active


async def _maybe_sync_standings(db: AsyncSession, client: ApiFootballClient) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_key = f"{STANDINGS_CACHE_KEY}:{today}"
    result = await db.execute(select(ApiCache).where(ApiCache.cache_key == cache_key))
    if result.scalar_one_or_none():
        return
    data = await client.fetch_standings()
    if data:
        expires = datetime.now(timezone.utc) + timedelta(hours=25)
        db.add(ApiCache(cache_key=cache_key, payload={"standings": data}, expires_at=expires))
        await db.flush()
        logger.info("Cached API-Football standings for %s (1 request)", today)


async def poll_once(db: AsyncSession) -> float:
    client = ApiFootballClient(db)
    if await client.is_halted():
        q = await client.get_quota_status()
        logger.warning(
            "API-Football polling halted - %s requests remaining, serving DB state",
            q.get("requests_remaining"),
        )
        return INTERVAL_LIVE_DEFAULT

    window = await compute_polling_window(db)
    if not window.active:
        return next_poll_interval(window)

    try:
        live_fixtures = await client.fetch_live_all()
    except QuotaHalted:
        return INTERVAL_LIVE_DEFAULT

    _state.last_poll_at = datetime.now(timezone.utc)
    code_map, id_map = await build_match_maps(db)
    burst_triggered = False

    for fx in live_fixtures:
        match, needs = await apply_fixture_snapshot(db, fx, code_map=code_map, id_map=id_map)
        if match and needs and match.api_fixture_id:
            api_home_id = ((fx.get("teams") or {}).get("home") or {}).get("id") or 0
            _state.pending_event_fetch[match.id] = api_home_id

    for match_id, api_home_id in list(_state.pending_event_fetch.items()):
        result = await db.execute(select(Match).where(Match.id == match_id))
        match = result.scalar_one_or_none()
        if not match or match.status != MatchStatus.LIVE or not match.api_fixture_id:
            _state.pending_event_fetch.pop(match_id, None)
            continue
        raw = await client.fetch_fixture_events(match.api_fixture_id)
        if raw and await merge_api_events(db, match, raw, api_home_id):
            burst_triggered = True
        _state.pending_event_fetch.pop(match_id, None)

    if burst_triggered:
        trigger_burst()

    await db.commit()
    window = await compute_polling_window(db)
    return next_poll_interval(window)


async def run_live_poller() -> None:
    logger.info("Live poller started (LIVE_DATA_MODE=api, league=1 season=2026)")
    while True:
        try:
            async with async_session() as db:
                interval = await poll_once(db)
        except Exception as exc:
            logger.exception("Live poller cycle failed: %s", exc)
            interval = INTERVAL_PRE_KICKOFF
        await asyncio.sleep(interval)


async def bootstrap_api_mode(db: AsyncSession) -> None:
    if not settings.effective_api_football_key:
        logger.warning("LIVE_DATA_MODE=api but API_FOOTBALL_KEY is empty - poller will idle")
        return
    client = ApiFootballClient(db)
    if await client.is_halted():
        logger.warning("API-Football quota already halted for today")
        return
    await link_api_fixture_ids(db, client)
    await _maybe_sync_standings(db, client)
    await db.flush()
