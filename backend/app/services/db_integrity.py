"""Verify relational integrity across KickOff26 schemas."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Bracket, Match, MatchEvent, Stadium, Team, User
from app.services.tournament_2026 import OFFICIAL_TEAMS

_OFFICIAL_CODES = {t["code"] for t in OFFICIAL_TEAMS}


async def verify_database_integrity(db: AsyncSession) -> list[str]:
    """Return a list of human-readable issues (empty = all checks passed)."""
    issues: list[str] = []

    team_rows = (await db.execute(select(Team.id, Team.code))).all()
    team_ids = {row.id for row in team_rows}
    team_codes = {row.code for row in team_rows}

    missing_official = sorted(_OFFICIAL_CODES - team_codes)
    if missing_official:
        issues.append(f"Missing official teams in DB: {', '.join(missing_official)}")

    stadium_ids = set((await db.execute(select(Stadium.id))).scalars().all())

    matches = (
        await db.execute(
            select(Match).options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.stadium),
            )
        )
    ).scalars().all()
    match_ids = {m.id for m in matches}

    for match in matches:
        if match.home_team_id not in team_ids:
            issues.append(f"Match {match.id}: invalid home_team_id {match.home_team_id}")
        if match.away_team_id not in team_ids:
            issues.append(f"Match {match.id}: invalid away_team_id {match.away_team_id}")
        if match.stadium_id is not None and match.stadium_id not in stadium_ids:
            issues.append(f"Match {match.id}: invalid stadium_id {match.stadium_id}")

    for match_id, event_id in (
        await db.execute(select(MatchEvent.match_id, MatchEvent.id))
    ).all():
        if match_id not in match_ids:
            issues.append(f"MatchEvent {event_id}: dangling match_id {match_id}")

    for user in (await db.execute(select(User))).scalars().all():
        if user.favorite_team_id is not None and user.favorite_team_id not in team_ids:
            issues.append(
                f"User {user.id}: invalid favorite_team_id {user.favorite_team_id}"
            )
        for tid in user.followed_team_ids or []:
            if tid not in team_ids:
                issues.append(f"User {user.id}: invalid followed_team_id {tid}")

    for bracket in (await db.execute(select(Bracket))).scalars().all():
        if bracket.user_id is None:
            continue
        if bracket.champion_team_id is not None and bracket.champion_team_id not in team_ids:
            issues.append(
                f"Bracket {bracket.id}: invalid champion_team_id {bracket.champion_team_id}"
            )

    return issues
