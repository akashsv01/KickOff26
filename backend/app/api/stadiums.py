"""Read-only stadium views: all venues and the matches hosted at each.

Reuses the existing stadiums table and matches.stadium_id - no new data sources.
Kickoffs are returned in UTC; the frontend localizes to the user's timezone.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Match, Stadium

router = APIRouter(prefix="/stadiums", tags=["stadiums"])


def _stadium_summary(stadium: Stadium, match_count: int) -> dict:
    return {
        "id": stadium.id,
        "name": stadium.name_en,
        "city": stadium.city_en,
        "country": stadium.country_en,
        "capacity": stadium.capacity,
        "match_count": match_count,
    }


def _stadium_match(match: Match) -> dict:
    return {
        "id": match.id,
        "home_team": {
            "id": match.home_team.id,
            "name": match.home_team.name,
            "code": match.home_team.code,
        },
        "away_team": {
            "id": match.away_team.id,
            "name": match.away_team.name,
            "code": match.away_team.code,
        },
        "home_score": match.home_score,
        "away_score": match.away_score,
        "minute": match.minute,
        "status": match.status.value,
        "stage": match.stage,
        "group_letter": match.group_letter,
        "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
    }


@router.get("")
async def list_stadiums(db: AsyncSession = Depends(get_db)):
    counts = dict(
        (
            await db.execute(
                select(Match.stadium_id, func.count())
                .where(Match.stadium_id.isnot(None))
                .group_by(Match.stadium_id)
            )
        ).all()
    )
    stadiums = (await db.execute(select(Stadium).order_by(Stadium.name_en))).scalars().all()
    return [_stadium_summary(s, counts.get(s.id, 0)) for s in stadiums]


@router.get("/{stadium_id}")
async def stadium_detail(stadium_id: int, db: AsyncSession = Depends(get_db)):
    stadium = (
        await db.execute(select(Stadium).where(Stadium.id == stadium_id))
    ).scalar_one_or_none()
    if not stadium:
        raise HTTPException(status_code=404, detail="Stadium not found")
    matches = (
        await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(Match.stadium_id == stadium_id)
            .order_by(Match.kickoff_at)
        )
    ).scalars().all()
    return {
        **_stadium_summary(stadium, len(matches)),
        "matches": [_stadium_match(m) for m in matches],
    }
