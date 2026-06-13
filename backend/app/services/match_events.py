"""Persist and load per-match event timelines in Postgres."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, MatchEvent
from app.services.matchday_alerts import (
    clean_player_name,
    event_key,
    filter_supported_events,
    is_supported_event,
)

logger = logging.getLogger(__name__)


def _clean_minute(value) -> int | None:
    """Preserve a real minute; never coerce a missing minute to 0."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def event_dict_to_row_fields(event: dict) -> dict:
    return {
        "event_type": event["type"],
        "minute": _clean_minute(event.get("minute")),
        "added_time": _clean_minute(event.get("added_time")),
        "team_side": event.get("team") or "",
        "player_name": clean_player_name(event.get("player")),
        "detail": str(event.get("detail") or ""),
    }


def event_row_to_dict(row: MatchEvent) -> dict:
    out: dict = {
        "type": row.event_type,
        "minute": row.minute,
        "team": row.team_side,
        "player": row.player_name,
    }
    if row.added_time is not None:
        out["added_time"] = row.added_time
    if row.detail:
        out["detail"] = row.detail
    return out


async def replace_side_goals(
    db: AsyncSession,
    match_id: int,
    team_side: str,
    scorers: list[dict],
) -> bool:
    """Replace ALL stored goal events for one side with a clean scorer list.

    Idempotent replace-the-set-per-side: if the stored goals already match
    ``scorers`` nothing changes (returns False); otherwise the side's goals are
    deleted and re-inserted from the clean list (returns True). This overwrites
    duplicates and stale/old-language versions instead of appending. ``scorers``
    items are ``{player_name, minute, added_time}`` from ``parse_scorers``.
    """
    existing = (
        await db.execute(
            select(MatchEvent).where(
                MatchEvent.match_id == match_id,
                MatchEvent.event_type == "goal",
                MatchEvent.team_side == team_side,
            )
        )
    ).scalars().all()

    # Defensive dedup of the incoming list (a glitchy feed could repeat a goal).
    seen: set[tuple] = set()
    clean: list[dict] = []
    for s in scorers:
        name = clean_player_name(s.get("player_name"))
        if not name:
            continue
        minute = _clean_minute(s.get("minute"))
        added = _clean_minute(s.get("added_time"))
        key = (name, minute, added)
        if key in seen:
            continue
        seen.add(key)
        clean.append({"player_name": name, "minute": minute, "added_time": added})

    existing_keys = {(e.player_name, e.minute, e.added_time) for e in existing}
    if existing_keys == seen:
        return False

    for row in existing:
        await db.delete(row)
    await db.flush()
    for c in clean:
        db.add(
            MatchEvent(
                match_id=match_id,
                event_type="goal",
                team_side=team_side,
                player_name=c["player_name"],
                minute=c["minute"],
                added_time=c["added_time"],
                detail="",
            )
        )
    await db.flush()
    return True


async def fetch_events_for_match(db: AsyncSession, match_id: int) -> list[dict]:
    result = await db.execute(
        select(MatchEvent)
        .where(MatchEvent.match_id == match_id)
        # NULL minutes (unknown) sort last and deterministically across dialects.
        .order_by(func.coalesce(MatchEvent.minute, 9999), MatchEvent.id)
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
        .order_by(MatchEvent.match_id, func.coalesce(MatchEvent.minute, 9999), MatchEvent.id)
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
            "minute": _clean_minute(event.get("minute")),
            "team": event.get("team") or "",
            "player": clean_player_name(event.get("player")),
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
