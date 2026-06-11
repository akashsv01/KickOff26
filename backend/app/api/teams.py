from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Team, User
from app.schemas import FollowTeamsRequest, TeamProfileResponse, TeamResponse
from app.services.team_roster_service import build_team_profile, resync_all_rosters
from app.services.tournament_2026 import OFFICIAL_TEAMS

router = APIRouter(prefix="/teams", tags=["teams"])
_OFFICIAL_CODES = {t["code"] for t in OFFICIAL_TEAMS}


@router.get("", response_model=list[TeamResponse])
async def list_teams(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Team).where(Team.code.in_(_OFFICIAL_CODES)).order_by(Team.group_letter, Team.code)
    )
    return [TeamResponse.model_validate(t) for t in result.scalars().all()]


@router.get("/{team_id}/profile", response_model=TeamProfileResponse)
async def team_profile(team_id: int, db: AsyncSession = Depends(get_db)):
    team = (
        await db.execute(
            select(Team).where(Team.id == team_id, Team.code.in_(_OFFICIAL_CODES))
        )
    ).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    profile = await build_team_profile(db, team)
    return TeamProfileResponse(team=TeamResponse.model_validate(team), **profile)


@router.post("/rosters/resync")
async def resync_rosters(
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Re-fetch Zafronix rosters (use force=true to refresh every team)."""
    count = await resync_all_rosters(db, force=force)
    await db.commit()
    return {"synced": count}


@router.post("/follow")
async def follow_teams(
    data: FollowTeamsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.followed_team_ids = data.team_ids
    await db.flush()
    return {"followed_team_ids": user.followed_team_ids}
