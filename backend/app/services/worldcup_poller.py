"""Backend live poller for the rezarahiminia World Cup 2026 API.

Single shared poller: one batched GET /get/games per tick while in an active window.
Clients never call the API; updates fan out over WebSocket from Postgres.

Rate limit: 500 req/60s per IP. At 25s live cadence that is ~2.4 games calls/min plus
occasional /get/groups - well under the cap even with ~6 simultaneous live matches.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session
from app.services.live_poller import compute_polling_window
from app.services.worldcup_api import WorldCupApiClient
from app.services.worldcup_live import (
    apply_game_snapshot,
    build_code_map,
    build_game_object_id_map,
    reconcile_all_games_from_api,
)
from app.services.worldcup_parse import api_object_id
from app.services.worldcup_poll_scope import should_apply_game
from app.services.worldcup_reset import reset_demo_fabrication_for_api_mode
from app.services.worldcup_sync import (
    load_teams_by_seq,
    sync_groups_snapshot,
    sync_worldcup_data,
)

logger = logging.getLogger(__name__)

_tick = 0


def _live_interval() -> float:
    return float(settings.worldcup_poll_live_seconds)


def _pre_kickoff_interval() -> float:
    return float(settings.worldcup_poll_pre_kickoff_seconds)


def _idle_max() -> float:
    return float(settings.worldcup_poll_idle_max_seconds)


def _groups_refresh_every() -> int:
    return max(1, settings.worldcup_groups_refresh_every)


async def _apply_games_batch(
    db: AsyncSession,
    games: list[dict],
    *,
    code_map,
    oid_map,
    teams_by_seq,
) -> int:
    now = datetime.now(timezone.utc)
    applied = 0
    for game in games:
        if not isinstance(game, dict):
            continue
        oid = api_object_id(game)
        if not oid:
            continue
        match = oid_map.get(oid)
        if not match or not should_apply_game(game, match, now=now):
            continue
        if await apply_game_snapshot(
            db,
            game,
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
        ):
            applied += 1
    return applied


async def poll_once(db: AsyncSession) -> float:
    global _tick
    client = WorldCupApiClient()
    if not client.configured:
        logger.warning("LIVE_DATA_MODE=api but WORLDCUP_API_TOKEN is empty - poller idling")
        return _idle_max()

    window = await compute_polling_window(db)
    if not window.active:
        return min(max(window.seconds_until_active, _pre_kickoff_interval()), _idle_max())

    teams_by_seq = await load_teams_by_seq(db)
    if not teams_by_seq:
        await sync_worldcup_data(db, client)
        teams_by_seq = await load_teams_by_seq(db)

    code_map = await build_code_map(db)
    oid_map = await build_game_object_id_map(db)

    games = await client.get_games()
    if games:
        applied = await _apply_games_batch(
            db,
            games,
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
        )
        if applied:
            logger.debug("WorldCup poll applied %s game snapshot(s)", applied)
    else:
        logger.debug("WorldCup poll skipped or empty games response - serving DB state")

    _tick += 1
    if window.in_live_window and _tick % _groups_refresh_every() == 0:
        await sync_groups_snapshot(db, client)

    await db.commit()

    window = await compute_polling_window(db)
    if window.in_live_window:
        return _live_interval()
    if window.active:
        return _pre_kickoff_interval()
    return min(max(window.seconds_until_active, _pre_kickoff_interval()), _idle_max())


async def run_worldcup_poller() -> None:
    logger.info(
        "WorldCup26 live poller started (LIVE_DATA_MODE=api, source=worldcup26.ir, "
        "live=%ss, pre_kickoff=%ss)",
        settings.worldcup_poll_live_seconds,
        settings.worldcup_poll_pre_kickoff_seconds,
    )
    while True:
        try:
            async with async_session() as db:
                interval = await poll_once(db)
        except Exception as exc:  # noqa: BLE001
            logger.exception("WorldCup poller cycle failed: %s", exc)
            interval = _pre_kickoff_interval()
        await asyncio.sleep(interval)


async def bootstrap_worldcup_mode(db: AsyncSession) -> None:
    """Startup: clear demo fabrication, sync reference data, baseline live state from API."""
    client = WorldCupApiClient()
    if not client.configured:
        logger.warning("LIVE_DATA_MODE=api but WORLDCUP_API_TOKEN is empty - skipping bootstrap")
        return
    reset_stats = await reset_demo_fabrication_for_api_mode(db)
    result = await sync_worldcup_data(db, client)
    games = await client.get_games()
    reconciled = await reconcile_all_games_from_api(db, games or [], emit_alerts=False)
    logger.info(
        "WorldCup bootstrap: reset=%s sync=%s reconciled_games=%s",
        reset_stats,
        result,
        reconciled,
    )
