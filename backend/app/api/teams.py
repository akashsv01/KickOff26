from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Team, User
from app.schemas import FollowTeamsRequest, TeamResponse
from app.services.tournament_2026 import OFFICIAL_TEAMS

router = APIRouter(prefix="/teams", tags=["teams"])
_OFFICIAL_CODES = {t["code"] for t in OFFICIAL_TEAMS}


@router.get("", response_model=list[TeamResponse])
async def list_teams(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Team).where(Team.code.in_(_OFFICIAL_CODES)).order_by(Team.group_letter, Team.code)
    )
    return [TeamResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/follow")
async def follow_teams(
    data: FollowTeamsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.followed_team_ids = data.team_ids
    await db.flush()
    return {"followed_team_ids": user.followed_team_ids}
