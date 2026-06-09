"""Data ingestion with API-Football (primary) and football-data.org (fallback)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ApiCache, Match, MatchStatus, Team
from app.services.data_sync import sync_tournament_data
from app.services.fixture_seed import seed_fixtures_from_json
from app.services.tournament_2026 import HOST_CITIES, STADIUM_TO_CITY


class DataIngestionService:
    """Unified data layer with Postgres caching."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_all(self, force: bool = False) -> dict:
        from app.services.openfootball import ensure_worldcup_cache

        ensure_worldcup_cache()
        result = await seed_fixtures_from_json(
            self.db, demo_live=settings.is_demo_live, force=force
        )
        if not result.get("skipped"):
            from app.services.data_sync import _merge_api_updates

            result["api_updated"] = await _merge_api_updates(self.db)
        elif settings.effective_api_football_key or settings.football_data_api_key:
            from app.services.data_sync import _merge_api_updates

            result["api_updated"] = await _merge_api_updates(self.db)
        return result

    async def get_cached(self, key: str) -> dict | None:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(ApiCache).where(ApiCache.cache_key == key, ApiCache.expires_at > now)
        )
        row = result.scalar_one_or_none()
        return row.payload if row else None

    async def set_cache(self, key: str, payload: dict, ttl: int) -> None:
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        result = await self.db.execute(select(ApiCache).where(ApiCache.cache_key == key))
        row = result.scalar_one_or_none()
        if row:
            row.payload = payload
            row.expires_at = expires
        else:
            self.db.add(ApiCache(cache_key=key, payload=payload, expires_at=expires))
        await self.db.flush()

    async def fetch_teams(self) -> list[Team]:
        result = await self.db.execute(select(Team).order_by(Team.group_letter, Team.code))
        return list(result.scalars().all())

    async def fetch_matches(self, live_only: bool = False) -> list[Match]:
        q = select(Match)
        if live_only:
            q = q.where(Match.status == MatchStatus.LIVE)
        result = await self.db.execute(q.order_by(Match.kickoff_at))
        return list(result.scalars().all())

    async def _fetch_api_football_fixtures(self) -> list[dict] | None:
        if not settings.effective_api_football_key:
            return None
        cache_key = "api_football:fixtures"
        cached = await self.get_cached(cache_key)
        if cached:
            return cached.get("items")

        data = await self._fetch_api_football("/fixtures", {"league": "1", "season": "2026"})
        if not data or "response" not in data:
            return None

        items = []
        for fx in data["response"]:
            fixture = fx.get("fixture", {})
            teams = fx.get("teams", {})
            goals = fx.get("goals", {})
            home = teams.get("home", {})
            away = teams.get("away", {})
            items.append(
                {
                    "external_id": f"af-{fixture.get('id')}",
                    "home_code": _normalize_code(home.get("name", ""), home.get("name", "")),
                    "away_code": _normalize_code(away.get("name", ""), away.get("name", "")),
                    "home_score": goals.get("home"),
                    "away_score": goals.get("away"),
                    "minute": fixture.get("status", {}).get("elapsed"),
                    "status": fixture.get("status", {}).get("short", "NS"),
                    "kickoff_at": fixture.get("date"),
                    "venue": fx.get("venue", {}).get("name"),
                }
            )

        await self.set_cache(cache_key, {"items": items}, settings.cache_ttl_matches)
        return items

    async def _fetch_football_data_fixtures(self) -> list[dict] | None:
        if not settings.football_data_api_key:
            return None
        cache_key = "football_data:fixtures"
        cached = await self.get_cached(cache_key)
        if cached:
            return cached.get("items")

        data = await self._fetch_football_data("/competitions/WC/matches")
        if not data or "matches" not in data:
            return None

        items = []
        for m in data["matches"]:
            home = m.get("homeTeam", {})
            away = m.get("awayTeam", {})
            score = m.get("score", {}).get("fullTime", {})
            items.append(
                {
                    "external_id": f"fd-{m.get('id')}",
                    "home_code": _normalize_code(home.get("tla", ""), home.get("name", "")),
                    "away_code": _normalize_code(away.get("tla", ""), away.get("name", "")),
                    "home_score": score.get("home"),
                    "away_score": score.get("away"),
                    "minute": m.get("minute"),
                    "status": m.get("status", "SCHEDULED"),
                    "kickoff_at": m.get("utcDate"),
                    "venue": m.get("venue"),
                }
            )

        await self.set_cache(cache_key, {"items": items}, settings.cache_ttl_matches)
        return items

    async def _fetch_api_football(self, endpoint: str, params: dict) -> dict | None:
        if not settings.effective_api_football_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://{settings.rapidapi_host}{endpoint}",
                    params=params,
                    headers={
                        "x-rapidapi-key": settings.effective_api_football_key,
                        "x-rapidapi-host": settings.rapidapi_host,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
        except httpx.HTTPError:
            pass
        return None

    async def _fetch_football_data(self, endpoint: str) -> dict | None:
        if not settings.football_data_api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://api.football-data.org/v4{endpoint}",
                    headers={"X-Auth-Token": settings.football_data_api_key},
                )
                if resp.status_code == 200:
                    return resp.json()
        except httpx.HTTPError:
            pass
        return None

    async def get_matches_for_itinerary(self) -> list[dict]:
        matches = await self.fetch_matches()
        result = []
        for m in matches:
            await self.db.refresh(m, ["home_team", "away_team"])
            city = m.city or "Unknown"
            city_meta = HOST_CITIES.get(city, {})
            lat = m.stadium_lat if m.stadium_lat else city_meta.get("lat", 0)
            lng = m.stadium_lng if m.stadium_lng else city_meta.get("lng", 0)
            result.append(
                {
                    "id": m.id,
                    "home_code": m.home_team.code,
                    "away_code": m.away_team.code,
                    "kickoff_at": m.kickoff_at,
                    "city": city,
                    "country": m.country or city_meta.get("country", "USA"),
                    "venue": m.venue or city_meta.get("stadium", "Stadium"),
                    "lat": lat,
                    "lng": lng,
                    "stage": m.stage or "group",
                }
            )
        return result


def _normalize_code(tla: str, name: str) -> str:
    if tla and len(tla) <= 4:
        return tla.upper()
    mapping = {
        "United States": "USA",
        "South Korea": "KOR",
        "Côte d'Ivoire": "CIV",
        "Cote d'Ivoire": "CIV",
        "DR Congo": "COD",
        "Bosnia and Herzegovina": "BIH",
        "Türkiye": "TUR",
        "Turkey": "TUR",
    }
    return mapping.get(name, name[:3].upper())
