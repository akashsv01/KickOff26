"""DEMO live loop — simulated scores/events for local development.

Runs only when LIVE_DATA_MODE=demo. Never calls API-Football (zero quota usage).
Emits the same supported event/alert types as api mode (see matchday_alerts.py).
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import async_session
from app.models import Match, MatchStatus
from app.services.matchday import (
    enrich_match_probs,
    ensure_demo_live_match,
    match_to_dict,
    _aware,
)
from app.services.matchday_alerts import (
    demo_build_event,
    demo_pick_event,
    emit_event_alerts,
    emit_prob_momentum,
    emit_status_alert,
)
from app.services.match_events import fetch_events_for_match, insert_new_events
from app.websocket.gateway import ws_manager

logger = logging.getLogger(__name__)

DEMO_TICK_SECONDS = 12

_halftime_alerted: set[int] = set()
_kickoff_alerted: set[int] = set()


async def _broadcast_match_update(db, match: Match, pre_probs: dict) -> None:
    events = await fetch_events_for_match(db, match.id)
    payload = {"type": "match_update", "match": match_to_dict(match, pre_probs, events=events)}
    await ws_manager.broadcast(ws_manager.match_channel(match.id), payload)
    await ws_manager.broadcast("matches:live", payload)


async def run_demo_live_loop() -> None:
    """Background task — DEMO mode only (simulated live match)."""
    logger.info("Demo live loop started (LIVE_DATA_MODE=demo — no API calls)")

    while True:
        await asyncio.sleep(DEMO_TICK_SECONDS)
        async with async_session() as db:
            try:
                result = await db.execute(
                    select(Match)
                    .options(selectinload(Match.home_team), selectinload(Match.away_team))
                    .where(Match.status == MatchStatus.LIVE)
                )
                live_matches = list(result.scalars().all())

                if not live_matches:
                    started = await ensure_demo_live_match(db)
                    if started:
                        live_matches = [started]
                    elif not settings.is_mock:
                        await db.commit()
                        continue

                if settings.is_mock and not live_matches:
                    now = datetime.now(timezone.utc)
                    sched = await db.execute(
                        select(Match)
                        .options(selectinload(Match.home_team), selectinload(Match.away_team))
                        .where(Match.status == MatchStatus.SCHEDULED)
                        .limit(3)
                    )
                    for m in sched.scalars().all():
                        kickoff = _aware(m.kickoff_at)
                        if kickoff and kickoff <= now:
                            m.status = MatchStatus.LIVE
                            m.home_score = 0
                            m.away_score = 0
                            m.minute = 1
                            await insert_new_events(db, m.id, [])
                            live_matches.append(m)
                            if m.id not in _kickoff_alerted:
                                _kickoff_alerted.add(m.id)
                                await emit_status_alert(
                                    m,
                                    "match_start_alert",
                                    f"KICK OFF: {m.home_team.code} vs {m.away_team.code}",
                                )

                for m in live_matches:
                    old_probs = {
                        "home": m.win_prob_home or 0.33,
                        "draw": m.win_prob_draw or 0.33,
                        "away": m.win_prob_away or 0.33,
                    }
                    prev_minute = m.minute or 0
                    m.minute = min(prev_minute + 3, 90)

                    if prev_minute < 45 <= m.minute and m.id not in _halftime_alerted:
                        _halftime_alerted.add(m.id)
                        await emit_status_alert(
                            m,
                            "match_halftime_alert",
                            f"HALF TIME: {m.home_team.code} {m.home_score or 0}-"
                            f"{m.away_score or 0} {m.away_team.code}",
                        )

                    ev_type = demo_pick_event()
                    if ev_type:
                        team = "home" if random.random() < 0.55 else "away"
                        event = demo_build_event(
                            ev_type,
                            m.minute,
                            team,
                            home_code=m.home_team.code,
                            away_code=m.away_team.code,
                        )
                        if ev_type == "goal" or (
                            ev_type == "penalty" and event.get("detail") == "scored"
                        ):
                            if team == "home":
                                m.home_score = (m.home_score or 0) + 1
                            else:
                                m.away_score = (m.away_score or 0) + 1
                        inserted = await insert_new_events(db, m.id, [event])
                        if inserted:
                            await emit_event_alerts(m, inserted)

                    events = await fetch_events_for_match(db, m.id)

                    if m.minute >= 90:
                        finishing = m.status == MatchStatus.LIVE
                        m.status = MatchStatus.FINISHED
                        if finishing:
                            await emit_status_alert(
                                m,
                                "match_end_alert",
                                f"FULL TIME: {m.home_team.code} {m.home_score}-"
                                f"{m.away_score} {m.away_team.code}",
                            )

                    enriched = await enrich_match_probs(m, events=events)
                    new_probs = enriched["probs"]
                    await emit_prob_momentum(m, old_probs, new_probs)
                    await _broadcast_match_update(db, m, enriched["pre_probs"])

                await db.commit()
            except Exception as exc:
                logger.warning("Demo live tick failed: %s", exc)
                await db.rollback()
