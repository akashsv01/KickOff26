"""Validate user team references against official tournament teams."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Team
from app.services.tournament_2026 import OFFICIAL_TEAMS

_OFFICIAL_CODES = {t["code"] for t in OFFICIAL_TEAMS}


async def validate_official_team_ids(db: AsyncSession, team_ids: list[int]) -> None:
    """Ensure every id exists and maps to one of the 48 official nations."""
    if not team_ids:
        return
    unique = list(dict.fromkeys(team_ids))
    result = await db.execute(select(Team.id, Team.code).where(Team.id.in_(unique)))
    rows = result.all()
    if len(rows) != len(unique):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more team ids are invalid",
        )
    invalid = [code for _, code in rows if code not in _OFFICIAL_CODES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team must be one of the official World Cup 2026 nations",
        )


def merge_followed_team_ids(
    favorite_team_id: int | None,
    followed_team_ids: list[int] | None,
) -> list[int]:
    """Favorite team is always included in the follow list."""
    ordered: list[int] = []
    if favorite_team_id is not None:
        ordered.append(favorite_team_id)
    for tid in followed_team_ids or []:
        if tid not in ordered:
            ordered.append(tid)
    return ordered
