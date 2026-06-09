"""Sync teams and fixtures from published JSON + optional live API scores."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, MatchStatus, Team
from app.config import settings
from app.services.fixture_seed import seed_fixtures_from_json
from app.services.tournament_2026 import STADIUM_TO_CITY


async def sync_tournament_data(db: AsyncSession, force: bool = False) -> dict:
    """Upsert published fixtures, then merge live API score updates when keys are set."""
    result = await seed_fixtures_from_json(db, demo_live=settings.is_demo_live, force=force)
    if result.get("skipped"):
        api_updated = await _merge_api_updates(db)
        return {"source": "fixtures_json+api", "api_updated": api_updated}
    api_updated = await _merge_api_updates(db)
    result["api_updated"] = api_updated
    return result


async def _merge_api_updates(db: AsyncSession) -> int:
    """Pull live scores/status from APIs and update matching fixtures."""
    from app.services.data_ingestion import DataIngestionService

    svc = DataIngestionService(db)
    updated = 0

    api_fixtures = await svc._fetch_api_football_fixtures()
    if not api_fixtures:
        api_fixtures = await svc._fetch_football_data_fixtures()

    if not api_fixtures:
        return 0

    code_map = {t.code: t for t in (await db.execute(select(Team))).scalars().all()}

    for item in api_fixtures:
        home_code = item.get("home_code")
        away_code = item.get("away_code")
        if not home_code or not away_code:
            continue
        if home_code not in code_map or away_code not in code_map:
            continue

        ext_id = item.get("external_id")
        result = await db.execute(select(Match).where(Match.external_id == ext_id))
        match = result.scalar_one_or_none()
        if not match:
            result = await db.execute(
                select(Match).where(
                    Match.home_team_id == code_map[home_code].id,
                    Match.away_team_id == code_map[away_code].id,
                )
            )
            match = result.scalar_one_or_none()

        if not match:
            continue

        if item.get("home_score") is not None:
            match.home_score = item["home_score"]
            match.away_score = item.get("away_score")
        if item.get("minute") is not None:
            match.minute = item["minute"]
        if item.get("status"):
            match.status = _map_status(item["status"])
        if item.get("kickoff_at"):
            match.kickoff_at = item["kickoff_at"]
        if item.get("venue"):
            match.venue = item["venue"]
            city = STADIUM_TO_CITY.get(item["venue"].lower())
            if city:
                from app.services.tournament_2026 import HOST_CITIES

                info = HOST_CITIES[city]
                match.city = city
                match.country = info["country"]
                match.stadium_lat = info["lat"]
                match.stadium_lng = info["lng"]
        updated += 1

    await db.flush()
    return updated


def _map_status(raw: str) -> MatchStatus:
    raw = raw.upper()
    if raw in ("LIVE", "IN_PLAY", "1H", "2H", "HT", "ET", "P"):
        return MatchStatus.LIVE
    if raw in ("FINISHED", "FT", "AET", "PEN"):
        return MatchStatus.FINISHED
    if raw in ("POSTPONED", "SUSPENDED", "CANCELLED"):
        return MatchStatus.POSTPONED
    return MatchStatus.SCHEDULED
