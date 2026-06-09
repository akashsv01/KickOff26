"""API-Football (RapidAPI) client with daily quota tracking.

All live score polling goes through this module — clients never call the API directly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ApiCache

logger = logging.getLogger(__name__)

QUOTA_CACHE_KEY = "api_football:quota"
LEAGUE_ID = 1
SEASON = 2026
QUOTA_SAFE_THRESHOLD = 15
BASE_URL = "https://{host}"

LIVE_SHORT_STATUSES = frozenset({"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"})
FINISHED_SHORT_STATUSES = frozenset({"FT", "AET", "PEN", "AWD", "WO"})


class QuotaHalted(Exception):
    """Raised when daily API quota is below the safe threshold."""


class ApiFootballClient:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._quota: dict | None = None

    @property
    def api_key(self) -> str:
        return settings.effective_api_football_key

    async def _load_quota(self) -> dict:
        if self._quota is not None:
            return self._quota
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(ApiCache).where(ApiCache.cache_key == QUOTA_CACHE_KEY)
        )
        row = result.scalar_one_or_none()
        if row and row.payload:
            self._quota = dict(row.payload)
            halted_until = self._quota.get("halted_until")
            if halted_until:
                until = datetime.fromisoformat(halted_until)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                if now < until:
                    return self._quota
                self._quota["halted"] = False
                self._quota.pop("halted_until", None)
            return self._quota
        self._quota = {
            "requests_remaining": None,
            "requests_limit": 100,
            "requests_used_today": 0,
            "halted": False,
            "last_updated": now.isoformat(),
        }
        return self._quota

    async def _save_quota(self) -> None:
        if self._quota is None:
            return
        self._quota["last_updated"] = datetime.now(timezone.utc).isoformat()
        expires = datetime.now(timezone.utc) + timedelta(days=2)
        result = await self.db.execute(select(ApiCache).where(ApiCache.cache_key == QUOTA_CACHE_KEY))
        row = result.scalar_one_or_none()
        if row:
            row.payload = self._quota
            row.expires_at = expires
        else:
            self.db.add(ApiCache(cache_key=QUOTA_CACHE_KEY, payload=self._quota, expires_at=expires))
        await self.db.flush()

    def _apply_rate_headers(self, headers: httpx.Headers) -> None:
        remaining = headers.get("x-ratelimit-requests-remaining")
        limit = headers.get("x-ratelimit-requests-limit")
        if self._quota is None:
            self._quota = {}
        if limit is not None:
            try:
                self._quota["requests_limit"] = int(limit)
            except ValueError:
                pass
        if remaining is not None:
            try:
                rem = int(remaining)
                self._quota["requests_remaining"] = rem
                self._quota["requests_used_today"] = (
                    self._quota.get("requests_limit", 100) - rem
                )
                if rem < QUOTA_SAFE_THRESHOLD:
                    self._quota["halted"] = True
                    tomorrow = datetime.now(timezone.utc).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ) + timedelta(days=1)
                    self._quota["halted_until"] = tomorrow.isoformat()
                    logger.warning(
                        "API-Football quota low (%s remaining) — halting polls until %s",
                        rem,
                        tomorrow.date(),
                    )
            except ValueError:
                pass

    async def get_quota_status(self) -> dict:
        q = await self._load_quota()
        return {
            "requests_remaining": q.get("requests_remaining"),
            "requests_limit": q.get("requests_limit", 100),
            "requests_used_today": q.get("requests_used_today"),
            "halted": bool(q.get("halted")),
            "halted_until": q.get("halted_until"),
        }

    async def is_halted(self) -> bool:
        q = await self._load_quota()
        return bool(q.get("halted"))

    async def request(self, endpoint: str, params: dict | None = None) -> dict | None:
        if not self.api_key:
            logger.warning("API_FOOTBALL_KEY not set — skipping request to %s", endpoint)
            return None
        q = await self._load_quota()
        if q.get("halted"):
            raise QuotaHalted(q.get("requests_remaining"))

        url = BASE_URL.format(host=settings.rapidapi_host) + endpoint
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    url,
                    params=params or {},
                    headers={
                        "x-rapidapi-key": self.api_key,
                        "x-rapidapi-host": settings.rapidapi_host,
                    },
                )
                self._apply_rate_headers(resp.headers)
                q["requests_used_today"] = (q.get("requests_used_today") or 0) + 1
                await self._save_quota()
                if resp.status_code != 200:
                    logger.warning("API-Football %s returned %s", endpoint, resp.status_code)
                    return None
                data = resp.json()
                if data.get("errors"):
                    logger.warning("API-Football errors: %s", data["errors"])
                    return None
                remaining = q.get("requests_remaining")
                if remaining is not None:
                    logger.info(
                        "API-Football %s OK — %s requests remaining today",
                        endpoint,
                        remaining,
                    )
                return data
        except httpx.HTTPError as exc:
            logger.warning("API-Football HTTP error on %s: %s", endpoint, exc)
            return None

    async def fetch_live_all(self) -> list[dict]:
        """Single request for every in-progress match worldwide."""
        data = await self.request("/fixtures", {"live": "all"})
        if not data:
            return []
        return data.get("response") or []

    async def fetch_season_fixtures(self) -> list[dict]:
        data = await self.request("/fixtures", {"league": LEAGUE_ID, "season": SEASON})
        if not data:
            return []
        return data.get("response") or []

    async def fetch_fixture_events(self, fixture_id: int) -> list[dict]:
        data = await self.request("/fixtures/events", {"fixture": fixture_id})
        if not data:
            return []
        return data.get("response") or []

    async def fetch_fixture_by_id(self, fixture_id: int) -> dict | None:
        """Single fixture bundle (events + lineups + statistics when published)."""
        data = await self.request("/fixtures", {"id": fixture_id})
        if not data:
            return None
        items = data.get("response") or []
        return items[0] if items else None

    async def fetch_standings(self) -> list[dict]:
        data = await self.request("/standings", {"league": LEAGUE_ID, "season": SEASON})
        if not data:
            return []
        return data.get("response") or []
