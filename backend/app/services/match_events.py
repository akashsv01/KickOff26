"""Persist and load per-match event timelines in Postgres."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, MatchEvent
from app.services.matchday_alerts import (
    event_key,
    filter_supported_events,
    is_supported_event,
    normalize_player_name,
)

logger = logging.getLogger(__name__)

UNKNOWN_PLAYER = "Unknown player"


def event_dict_to_row_fields(event: dict) -> dict:
    return {
        "event_type": event["type"],
        "minute": int(event.get("minute") or 0),
        "team_side": event.get("team") or "",
        "player_name": normalize_player_name(event.get("player")),
        "detail": str(event.get("detail") or ""),
    }


def event_row_to_dict(row: MatchEvent) -> dict:
    out: dict = {
        "type": row.event_type,
        "minute": row.minute,
        "team": row.team_side,
        "player": row.player_name,
    }
    if row.detail:
        out["detail"] = row.detail
    return out


async def fetch_events_for_match(db: AsyncSession, match_id: int) -> list[dict]:
    result = await db.execute(
        select(MatchEvent)
        .where(MatchEvent.match_id == match_id)
        .order_by(MatchEvent.minute, MatchEvent.id)
    )
    return [event_row_to_dict(row) for row in result.scalars().all()]


async def fetch_events_by_match_ids(
    db: AsyncSession, match_ids: list[int]
) -> dict[int, list[dict]]:
    if not match_ids:
        return {}
    result = await db.execute(
        select(MatchEvent)
        .where(MatchEvent.match_id.in_(match_ids))
        .order_by(MatchEvent.match_id, MatchEvent.minute, MatchEvent.id)
    )
    out: dict[int, list[dict]] = {mid: [] for mid in match_ids}
    for row in result.scalars().all():
        out[row.match_id].append(event_row_to_dict(row))
    return out


async def insert_new_events(
    db: AsyncSession,
    match_id: int,
    events: list[dict],
) -> list[dict]:
    """Insert only events not already stored. Returns newly inserted event dicts."""
    existing = await fetch_events_for_match(db, match_id)
    seen = {event_key(e) for e in existing}
    inserted: list[dict] = []

    for event in filter_supported_events(events):
        if not is_supported_event(event):
            continue
        normalized = {
            "type": event["type"],
            "minute": int(event.get("minute") or 0),
            "team": event.get("team") or "",
            "player": normalize_player_name(event.get("player")),
            **({"detail": str(event.get("detail"))} if event.get("detail") else {}),
        }
        key = event_key(normalized)
        if key in seen:
            continue
        fields = event_dict_to_row_fields(normalized)
        row = MatchEvent(match_id=match_id, **fields)
        db.add(row)
        seen.add(key)
        inserted.append(normalized)
    if inserted:
        await db.flush()
    return inserted


async def migrate_json_events_if_needed(db: AsyncSession, match: Match) -> None:
    """One-time backfill from legacy Match.events JSON into match_events."""
    existing = await fetch_events_for_match(db, match.id)
    if existing:
        return
    legacy = match.events or []
    if not legacy:
        return
    await insert_new_events(db, match.id, legacy)
    logger.info("Migrated %s legacy JSON events for match %s", len(legacy), match.id)
