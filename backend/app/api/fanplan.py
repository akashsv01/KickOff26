from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Team, User
from app.schemas import ItineraryRequest, ItineraryResponse
from app.services.data_ingestion import DataIngestionService
from app.services.itinerary import get_host_cities, optimize_itinerary

router = APIRouter(prefix="/fanplan", tags=["fanplan"])


@router.get("/cities")
async def host_cities():
    return get_host_cities()


@router.post("/itinerary", response_model=ItineraryResponse)
async def generate_itinerary(
    data: ItineraryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ingestion = DataIngestionService(db)
    matches = await ingestion.get_matches_for_itinerary()

    result = await db.execute(select(Team).where(Team.id.in_(data.team_ids)))
    teams = result.scalars().all()
    team_codes = {t.code for t in teams}

    plan = optimize_itinerary(
        matches,
        team_codes,
        max_cities=data.max_cities,
        budget_usd=data.budget_usd,
    )
    return ItineraryResponse(**plan)
