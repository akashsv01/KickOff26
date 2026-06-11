"""Durable match lineups - fetch-once at ~10 min pre-kickoff, store in Postgres."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Match, MatchLineup, MatchStatus
from app.services.matchday_alerts import UNKNOWN_PLAYER
from app.services.openfootball import OFFICIAL_EXTERNAL_PREFIX
from app.services.squads import build_demo_lineup_package

LINEUP_FETCH_BEFORE = timedelta(minutes=10)
LINEUP_RETRY_DELAY = timedelta(minutes=4)
LINEUP_WINDOW_AFTER = timedelta(minutes=15)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_player(entry: dict) -> dict:
    player = entry.get("player") or {}
    number = player.get("number")
    return {
        "number": int(number) if number is not None else 0,
        "name": (player.get("name") or "").strip() or UNKNOWN_PLAYER,
        "position": (player.get("pos") or "").strip(),
        "grid": (player.get("grid") or "").strip(),
    }


def parse_lineup_side(side: dict) -> dict:
    coach = ((side.get("coach") or {}).get("name") or "").strip()
    formation = (side.get("formation") or "").strip()
    starting_xi = [_parse_player(entry) for entry in (side.get("startXI") or [])]
    bench = [_parse_player(entry) for entry in (side.get("substitutes") or [])]
    return {
        "formation": formation,
        "coach": coach,
        "starting_xi": starting_xi,
        "bench": bench,
    }


def parse_fixture_lineups(fixture_bundle: dict) -> tuple[dict, dict] | None:
    """Map API-Football bundled fixture lineups to home/away side payloads."""
    lineups = fixture_bundle.get("lineups") or []
    if not lineups:
        return None

    teams = fixture_bundle.get("teams") or {}
    home_id = (teams.get("home") or {}).get("id")
    away_id = (teams.get("away") or {}).get("id")
    home_side: dict | None = None
    away_side: dict | None = None

    for entry in lineups:
        team_id = (entry.get("team") or {}).get("id")
        parsed = parse_lineup_side(entry)
        if team_id == home_id:
            home_side = parsed
        elif team_id == away_id:
            away_side = parsed

    if not home_side or not away_side:
        return None
    if not home_side["starting_xi"] or not away_side["starting_xi"]:
        return None
    return home_side, away_side


def lineup_has_starters(row: MatchLineup | None) -> bool:
    return bool(row and row.fetch_status == "ready" and row.home_xi and row.away_xi)


async def get_lineup_row(db: AsyncSession, match_id: int) -> MatchLineup | None:
    result = await db.execute(select(MatchLineup).where(MatchLineup.match_id == match_id))
    return result.scalar_one_or_none()


async def store_lineup(
    db: AsyncSession,
    match_id: int,
    home: dict,
    away: dict,
    *,
    source: str = "api",
) -> MatchLineup:
    now = datetime.now(timezone.utc)
    row = await get_lineup_row(db, match_id)
    if row is None:
        row = MatchLineup(match_id=match_id)
        db.add(row)

    row.home_formation = home.get("formation") or None
    row.away_formation = away.get("formation") or None
    row.home_coach = home.get("coach") or None
    row.away_coach = away.get("coach") or None
    row.home_xi = home.get("starting_xi") or []
    row.away_xi = away.get("starting_xi") or []
    row.home_bench = home.get("bench") or []
    row.away_bench = away.get("bench") or []
    row.source = source
    row.fetched_at = now
    row.fetch_attempts = max(row.fetch_attempts or 0, 1)
    row.fetch_status = "ready"
    row.retry_after = None
    await db.flush()
    return row


async def store_demo_lineup_for_match(db: AsyncSession, match: Match) -> MatchLineup:
    home = build_demo_lineup_package(match.home_team.code, match.home_team.name)
    away = build_demo_lineup_package(match.away_team.code, match.away_team.name)
    return await store_lineup(db, match.id, home, away, source="demo")


def lineup_to_detail_fields(row: MatchLineup | None) -> dict:
    """Shape consumed by match detail API and frontend."""
    empty = {
        "home_lineup": [],
        "away_lineup": [],
        "lineups": None,
    }
    # Only expose lineups from a verified API source — never demo/placeholder data.
    if not row or row.source != "api" or not lineup_has_starters(row):
        return empty
    assert row is not None
    return {
        "home_lineup": row.home_xi,
        "away_lineup": row.away_xi,
        "lineups": {
            "home": {
                "formation": row.home_formation,
                "coach": row.home_coach,
                "starting_xi": row.home_xi,
                "bench": row.home_bench,
            },
            "away": {
                "formation": row.away_formation,
                "coach": row.away_coach,
                "starting_xi": row.away_xi,
                "bench": row.away_bench,
            },
        },
    }


async def clear_stored_lineups(db: AsyncSession) -> int:
    """Remove cached lineups (demo placeholders or stale rows)."""
    rows = (await db.execute(select(MatchLineup))).scalars().all()
    for row in rows:
        await db.delete(row)
    return len(rows)


async def ensure_demo_lineups(db: AsyncSession) -> int:
    """Deprecated: demo lineups are no longer seeded or shown."""
    return await clear_stored_lineups(db)


def in_lineup_fetch_window(match: Match, now: datetime) -> bool:
    kickoff = _aware(match.kickoff_at)
    if kickoff is None:
        return False
    window_start = kickoff - LINEUP_FETCH_BEFORE
    window_end = kickoff + LINEUP_WINDOW_AFTER
    return window_start <= now <= window_end


async def matches_needing_lineup_fetch(db: AsyncSession) -> list[Match]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(
            Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"),
            Match.api_fixture_id.isnot(None),
            Match.status.in_([MatchStatus.SCHEDULED, MatchStatus.LIVE]),
        )
        .order_by(Match.kickoff_at)
    )
    out: list[Match] = []
    for match in result.scalars().all():
        if not in_lineup_fetch_window(match, now):
            continue
        row = await get_lineup_row(db, match.id)
        if lineup_has_starters(row):
            continue
        if row and row.fetch_status == "unavailable":
            continue
        if row and row.fetch_status == "retry" and row.retry_after and now < _aware(row.retry_after):
            continue
        out.append(match)
    return out


async def _get_or_create_fetch_row(db: AsyncSession, match_id: int) -> MatchLineup:
    row = await get_lineup_row(db, match_id)
    if row is None:
        row = MatchLineup(match_id=match_id, fetch_status="retry")
        db.add(row)
        await db.flush()
    return row


async def _mark_empty_fetch(db: AsyncSession, row: MatchLineup) -> None:
    now = datetime.now(timezone.utc)
    row.fetch_attempts = (row.fetch_attempts or 0) + 1
    if row.fetch_attempts < 2:
        row.fetch_status = "retry"
        row.retry_after = now + LINEUP_RETRY_DELAY
    else:
        row.fetch_status = "unavailable"
        row.retry_after = None
    await db.flush()


async def fetch_and_store_lineup(
    db: AsyncSession,
    match: Match,
    client=None,
) -> bool:
    """One bundled fixtures?id= call; returns True when starting XIs were stored."""
    from app.services.api_football import ApiFootballClient
    from app.services.matchday_live import merge_api_events

    if client is None:
        client = ApiFootballClient(db)
    if not match.api_fixture_id:
        return False

    row = await get_lineup_row(db, match.id)
    if lineup_has_starters(row):
        return True

    bundle = await client.fetch_fixture_by_id(match.api_fixture_id)
    if not bundle:
        return False

    events = bundle.get("events") or []
    if events:
        teams = bundle.get("teams") or {}
        api_home_id = (teams.get("home") or {}).get("id")
        if api_home_id:
            await merge_api_events(db, match, events, api_home_id)

    parsed = parse_fixture_lineups(bundle)
    if parsed:
        home, away = parsed
        await store_lineup(db, match.id, home, away, source="api")
        return True

    row = await _get_or_create_fetch_row(db, match.id)
    await _mark_empty_fetch(db, row)
    return False
