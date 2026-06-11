"""Fetch, cache, and serve Zafronix team rosters from Postgres."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Team, TeamRoster
from app.services.team_local_data import coach_from_local_json, player_to_watch_from_local_json
from app.services.team_name_resolve import zafronix_slug_for_team
from app.services.zafronix_api import ZafronixApiClient, map_zafronix_position

logger = logging.getLogger(__name__)

POSITION_ORDER = ("GK", "DEF", "MID", "FWD", "OTHER")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(row: TeamRoster | None) -> bool:
    if row is None or row.fetch_status != "ready" or row.fetched_at is None:
        return False
    age = _utcnow() - row.fetched_at
    return age < timedelta(hours=settings.zafronix_roster_fresh_hours)


def _can_retry(row: TeamRoster | None) -> bool:
    if row is None:
        return True
    if row.fetch_status == "ready" and _is_fresh(row):
        return False
    if row.retry_after is None:
        return True
    return _utcnow() >= row.retry_after


def resolve_group_position(player: dict) -> str:
    """Derive squad bucket from stored raw_position (preferred) or legacy position."""
    raw = player.get("raw_position")
    if raw:
        return map_zafronix_position(str(raw))
    pos = str(player.get("position") or "MID").upper().strip()
    if pos in POSITION_ORDER:
        return pos
    return map_zafronix_position(pos)


def players_need_raw_position_refresh(players: list) -> bool:
    """Cached rosters without raw_position used stale mapping and must be re-fetched."""
    if not players:
        return False
    return any(isinstance(p, dict) and not p.get("raw_position") for p in players)


def group_players_by_position(players: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {pos: [] for pos in POSITION_ORDER}
    for player in players:
        pos = resolve_group_position(player)
        if pos not in grouped:
            grouped[pos] = []
        grouped[pos].append(player)
    for pos in grouped:
        grouped[pos].sort(
            key=lambda p: (p.get("jersey") is None, p.get("jersey") or 999, p.get("name", ""))
        )
    return grouped


async def get_roster_row(db: AsyncSession, team_id: int) -> TeamRoster | None:
    return (
        await db.execute(select(TeamRoster).where(TeamRoster.team_id == team_id))
    ).scalar_one_or_none()


async def sync_team_roster(db: AsyncSession, team: Team, *, force: bool = False) -> TeamRoster:
    row = await get_roster_row(db, team.id)
    if not force and row and _is_fresh(row):
        return row

    if not force and row and not _can_retry(row):
        return row

    client = ZafronixApiClient()
    slug = zafronix_slug_for_team(team)
    now = _utcnow()

    if not client.configured:
        if row is None:
            row = TeamRoster(team_id=team.id, zafronix_slug=slug)
            db.add(row)
        row.fetch_status = "unavailable"
        row.players = []
        row.coach = None
        row.fetched_at = now
        row.retry_after = now + timedelta(hours=settings.zafronix_roster_retry_hours)
        row.error_message = "Zafronix API key not configured"
        await db.flush()
        return row

    result = await client.get_roster(slug)

    if row is None:
        row = TeamRoster(team_id=team.id, zafronix_slug=slug)
        db.add(row)
    else:
        row.zafronix_slug = slug

    row.fetched_at = now
    row.coach = result.get("coach")
    row.error_message = result.get("error")

    if result.get("ok") and result.get("players"):
        row.players = result["players"]
        row.fetch_status = "ready"
        row.retry_after = None
    elif result.get("status_code") == 429:
        if row.fetch_status != "ready":
            row.fetch_status = "unavailable"
        row.retry_after = now + timedelta(hours=1)
    else:
        row.players = []
        row.fetch_status = "unavailable"
        row.retry_after = now + timedelta(hours=settings.zafronix_roster_retry_hours)

    await db.flush()
    return row


def resolve_coach(team: Team, roster_row: TeamRoster | None) -> tuple[str | None, str | None]:
    if roster_row and roster_row.coach:
        return roster_row.coach, "zafronix"
    local = coach_from_local_json(team)
    if local:
        return local, "local"
    return None, None


def squad_status(roster_row: TeamRoster | None) -> str:
    if roster_row is None:
        return "loading"
    if roster_row.fetch_status == "ready" and roster_row.players:
        return "ready"
    if roster_row.fetch_status == "unavailable":
        return "unavailable"
    if roster_row.fetch_status == "ready" and not roster_row.players:
        return "unavailable"
    return "loading"


async def build_team_profile(db: AsyncSession, team: Team, *, allow_fetch: bool = True) -> dict:
    row = await get_roster_row(db, team.id)

    if allow_fetch and row and row.fetch_status == "ready" and players_need_raw_position_refresh(row.players or []):
        row = await sync_team_roster(db, team, force=True)

    if allow_fetch and not _is_fresh(row) and _can_retry(row):
        row = await sync_team_roster(db, team)

    coach_name, coach_source = resolve_coach(team, row)
    status = squad_status(row)
    players = row.players if row and row.fetch_status == "ready" else []
    ptw = player_to_watch_from_local_json(team)

    return {
        "coach": coach_name,
        "coach_source": coach_source,
        "coach_display": coach_name or "TBD",
        "squad": {
            "status": status,
            "players_by_position": group_players_by_position(players) if status == "ready" else {},
            "fetched_at": row.fetched_at.isoformat() if row and row.fetched_at else None,
        },
        "player_to_watch": ptw,
    }


async def resync_all_rosters(db: AsyncSession, *, force: bool = False) -> int:
    """Re-fetch every team roster from Zafronix (admin / one-off cache bust)."""
    if not settings.has_zafronix_key:
        return 0

    teams = (
        await db.execute(select(Team).order_by(Team.group_letter, Team.code))
    ).scalars().all()

    synced = 0
    for team in teams:
        if not force:
            row = await get_roster_row(db, team.id)
            if _is_fresh(row) and row and not players_need_raw_position_refresh(row.players or []):
                continue
        await sync_team_roster(db, team, force=True)
        synced += 1
    return synced


async def prefetch_stale_rosters(db: AsyncSession, *, limit: int = 3) -> int:
    """Background refresh for a few stale/missing rosters (rate-limit friendly)."""
    if not settings.has_zafronix_key:
        return 0

    teams = (
        await db.execute(select(Team).order_by(Team.group_letter, Team.code))
    ).scalars().all()

    synced = 0
    for team in teams:
        if synced >= limit:
            break
        row = await get_roster_row(db, team.id)
        if _is_fresh(row):
            continue
        if not _can_retry(row):
            continue
        await sync_team_roster(db, team)
        synced += 1
    return synced
