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

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings
from app.services.worldcup_rate_limit import get_rate_stats, record_429, record_request, wait_if_needed

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://worldcup26.ir"
CONNECT_TIMEOUT = 15.0
READ_TIMEOUT = 60.0
MAX_ATTEMPTS = 4
RETRY_BACKOFF_BASE = 0.75

_shared_client: httpx.AsyncClient | None = None


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


def _safe_body_preview(resp: httpx.Response, limit: int = 400) -> str:
    try:
        text = resp.text
    except Exception as exc:
        return f"<unreadable body: {type(exc).__name__}>"
    text = text.replace("\n", " ").strip()
    return text[:limit] if text else "<empty>"


def _log_request_failure(
    *,
    path: str,
    url: str,
    exc: BaseException | None = None,
    resp: httpx.Response | None = None,
    attempt: int | None = None,
) -> None:
    parts = [f"WorldCup API failure GET {path}"]
    if attempt is not None:
        parts.append(f"attempt={attempt}/{MAX_ATTEMPTS}")
    parts.append(f"url={url}")
    if resp is not None:
        parts.append(f"status={resp.status_code}")
        parts.append(f"body={_safe_body_preview(resp)}")
    if exc is not None:
        parts.append(f"error={type(exc).__name__}")
        detail = str(exc).strip() or repr(exc)
        parts.append(f"detail={detail}")
        if exc.__cause__:
            parts.append(f"cause={type(exc.__cause__).__name__}:{exc.__cause__!r}")
    logger.warning(" | ".join(parts))


async def _shared_http_client(*, force_new: bool = False) -> httpx.AsyncClient:
    """Reuse one HTTP/2 client; recreate when connections go stale (EndOfStream on Windows)."""
    global _shared_client
    if force_new and _shared_client is not None:
        try:
            await _shared_client.aclose()
        except Exception:
            pass
        _shared_client = None
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT),
            http2=True,
            limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
        )
    return _shared_client


async def close_shared_http_client() -> None:
    global _shared_client
    if _shared_client is not None:
        await _shared_client.aclose()
        _shared_client = None


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

    async def _try_refresh_token(self) -> bool:
        email = settings.worldcup_api_email
        password = settings.worldcup_api_password
        if not email or not password:
            logger.error(
                "WorldCup API token rejected - set WORLDCUP_API_TOKEN or "
                "WORLDCUP_API_EMAIL/PASSWORD for auto re-authentication"
            )
            return False
        token = await self.authenticate(email, password)
        if not token:
            return False
        self.token = token
        logger.warning(
            "WorldCup API token refreshed via authenticate - "
            "update WORLDCUP_API_TOKEN in .env to persist across restarts"
        )
        return True

    async def _get(self, path: str, params: dict | None = None) -> Any:
        if not self.token:
            logger.warning("WORLDCUP_API_TOKEN not set - skipping GET %s", path)
            return None
        if not await wait_if_needed():
            logger.warning("WorldCup API rate guard active - skipping GET %s", path)
            return None

        url = f"{self.base_url}{path}"
        refreshed = False
        reset_client = False

        for attempt in range(1, MAX_ATTEMPTS + 1):
            client = await _shared_http_client(force_new=reset_client)
            reset_client = False
            try:
                resp = await client.get(url, params=params or {}, headers=self._headers())
            except httpx.HTTPError as exc:
                _log_request_failure(path=path, url=url, exc=exc, attempt=attempt)
                reset_client = True
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
                    continue
                return None

            record_request()

            if resp.status_code in (401, 403):
                _log_request_failure(path=path, url=url, resp=resp, attempt=attempt)
                if not refreshed and resp.status_code == 401:
                    refreshed = await self._try_refresh_token()
                    if refreshed:
                        continue
                return None

            if resp.status_code == 429:
                record_429()
                _log_request_failure(path=path, url=url, resp=resp, attempt=attempt)
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** attempt))
                    continue
                return None

            if resp.status_code >= 500:
                _log_request_failure(path=path, url=url, resp=resp, attempt=attempt)
                reset_client = True
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
                    continue
                return None

            if resp.status_code != 200:
                _log_request_failure(path=path, url=url, resp=resp, attempt=attempt)
                return None

            try:
                return resp.json()
            except ValueError as exc:
                _log_request_failure(path=path, url=url, resp=resp, exc=exc, attempt=attempt)
                return None

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
            client = await _shared_http_client()
            resp = await client.post(url, json={"email": email, "password": password})
        except httpx.HTTPError as exc:
            _log_request_failure(path="/auth/authenticate", url=url, exc=exc)
            return None
        if resp.status_code not in (200, 201):
            _log_request_failure(path="/auth/authenticate", url=url, resp=resp)
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
            client = await _shared_http_client()
            resp = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            _log_request_failure(path="/auth/register", url=url, exc=exc)
            return None
        if resp.status_code not in (200, 201):
            _log_request_failure(path="/auth/register", url=url, resp=resp)
            return None
        body = resp.json()
        if isinstance(body, dict):
            return body.get("token") or body.get("access_token")
        return None
