"""rezarahiminia World Cup 2026 API client (https://worldcup26.ir).

Real live-data source for LIVE_DATA_MODE=api. All polling happens on the backend;
clients never call this API directly. The API uses JWT bearer auth; the token is
read from settings (WORLDCUP_API_TOKEN) and is valid for 84 days.

Endpoints used (GET unless noted):
  POST /auth/register, POST /auth/authenticate  -> obtain token
  /get/teams            (?group=A filters by group)
  /get/team/{id}
  /get/groups           (group standings)
  /get/games            (all matches; includes live scores + scorers)
  /get/game/{id}        (single match, for a focused live match)
  /get/stadiums

The match payload exposes: home_score, away_score, home_scorers, away_scorers,
time_elapsed, finished. NOT available (per the maintainer): cards, substitutions,
squads/lineups, and any SSE/WebSocket. We never fabricate those as real.

Rate limit: 500 requests / 60s per IP. Cadence is controlled by the poller.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.services.worldcup_rate_limit import get_rate_stats, record_429, record_request, wait_if_needed

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://worldcup26.ir"
REQUEST_TIMEOUT = 20


def _unwrap(data: Any, *keys: str) -> Any:
    """Tolerate response shapes like a bare list, {data: ...}, or {teams: ...}."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in (*keys, "data", "result", "results", "items"):
            if key in data and data[key] is not None:
                return data[key]
        return data
    return data


class WorldCupApiClient:
    """Thin async client for the rezarahiminia World Cup 2026 API."""

    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self.token = token if token is not None else settings.worldcup_api_token
        self.base_url = (base_url or settings.worldcup_api_base or DEFAULT_BASE_URL).rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _get(self, path: str, params: dict | None = None) -> Any:
        if not self.token:
            logger.warning("WORLDCUP_API_TOKEN not set - skipping GET %s", path)
            return None
        if not await wait_if_needed():
            logger.warning("WorldCup API rate guard active - skipping GET %s", path)
            return None
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, params=params or {}, headers=self._headers())
        except httpx.HTTPError as exc:
            logger.warning("WorldCup API HTTP error on %s: %s", path, exc)
            return None
        record_request()
        if resp.status_code == 401:
            logger.error("WorldCup API 401 on %s - token invalid/expired (re-authenticate)", path)
            return None
        if resp.status_code == 429:
            record_429()
            return None
        if resp.status_code != 200:
            logger.warning("WorldCup API %s returned %s", path, resp.status_code)
            return None
        try:
            return resp.json()
        except ValueError:
            logger.warning("WorldCup API %s returned non-JSON body", path)
            return None

    @staticmethod
    def rate_stats() -> dict:
        return get_rate_stats()

    # ---- Reference data -------------------------------------------------

    async def get_teams(self, group: str | None = None) -> list[dict]:
        params = {"group": group} if group else None
        data = await self._get("/get/teams", params)
        out = _unwrap(data, "teams")
        return out if isinstance(out, list) else []

    async def get_team(self, team_id: int | str) -> dict | None:
        data = await self._get(f"/get/team/{team_id}")
        out = _unwrap(data, "team")
        return out if isinstance(out, dict) else None

    async def get_groups(self) -> list[dict]:
        data = await self._get("/get/groups")
        out = _unwrap(data, "groups")
        return out if isinstance(out, list) else []

    async def get_stadiums(self) -> list[dict]:
        data = await self._get("/get/stadiums")
        out = _unwrap(data, "stadiums")
        return out if isinstance(out, list) else []

    # ---- Matches --------------------------------------------------------

    async def get_games(self) -> list[dict]:
        data = await self._get("/get/games")
        out = _unwrap(data, "games", "matches")
        return out if isinstance(out, list) else []

    async def get_game(self, game_id: int | str) -> dict | None:
        data = await self._get(f"/get/game/{game_id}")
        out = _unwrap(data, "game", "match")
        return out if isinstance(out, dict) else None

    # ---- Auth helpers (used by scripts/get_worldcup_token.py) -----------

    async def authenticate(self, email: str, password: str) -> str | None:
        """POST /auth/authenticate -> JWT token (valid ~84 days)."""
        url = f"{self.base_url}/auth/authenticate"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(url, json={"email": email, "password": password})
        except httpx.HTTPError as exc:
            logger.warning("WorldCup API authenticate error: %s", exc)
            return None
        if resp.status_code not in (200, 201):
            logger.warning("WorldCup API authenticate returned %s: %s", resp.status_code, resp.text[:200])
            return None
        body = resp.json()
        if isinstance(body, dict):
            return body.get("token") or body.get("access_token") or (_unwrap(body, "token"))
        return None

    async def register(self, email: str, password: str, name: str | None = None) -> str | None:
        """POST /auth/register -> JWT token (valid ~84 days)."""
        url = f"{self.base_url}/auth/register"
        payload: dict[str, Any] = {"email": email, "password": password}
        if name:
            payload["name"] = name
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("WorldCup API register error: %s", exc)
            return None
        if resp.status_code not in (200, 201):
            logger.warning("WorldCup API register returned %s: %s", resp.status_code, resp.text[:200])
            return None
        body = resp.json()
        if isinstance(body, dict):
            return body.get("token") or body.get("access_token")
        return None
