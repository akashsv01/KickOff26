from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.services.matchday import (
    get_all_matches,
    get_following_next,
    get_match_days,
    get_match_detail,
)

router = APIRouter(prefix="/matchday", tags=["matchday"])


@router.get("/matches")
async def list_matches(db: AsyncSession = Depends(get_db)):
    return await get_all_matches(db)


@router.get("/matches/{match_id}")
async def get_match(match_id: int, db: AsyncSession = Depends(get_db)):
    detail = await get_match_detail(db, match_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Match not found")
    return detail


@router.get("/days")
async def match_days(db: AsyncSession = Depends(get_db)):
    return await get_match_days(db)


@router.get("/following")
async def following_feed(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_following_next(db, user.followed_team_ids or [])


@router.get("/live")
async def live_matches(db: AsyncSession = Depends(get_db)):
    all_matches = await get_all_matches(db)
    return [m for m in all_matches if m["status"] == "live"]
