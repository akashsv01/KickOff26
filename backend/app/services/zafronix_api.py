"""Zafronix World Cup roster API client."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

import re

from app.config import settings

logger = logging.getLogger(__name__)

ZAFRONIX_POSITION_MAP = {
    "GK": "GK",
    "DF": "DEF",
    "DEF": "DEF",
    "MF": "MID",
    "MID": "MID",
    "FW": "FWD",
    "FWD": "FWD",
}


def map_zafronix_position(raw: str | None) -> str:
    """Map Zafronix/raw position codes to squad group buckets."""
    key = (raw or "").upper().strip()
    if not key:
        return "MID"
    return ZAFRONIX_POSITION_MAP.get(key, "OTHER")


def _parse_player_name(raw: str) -> tuple[str, bool]:
    name = raw.strip()
    if re.search(r"\(captain\)", name, flags=re.I):
        display = re.sub(r"\s*\(captain\)\s*", "", name, flags=re.I).strip()
        return display, True
    return name, False


class ZafronixApiClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.zafronix_api_key
        self.base_url = (base_url or settings.zafronix_api_base).rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Accept": "application/json"}

    async def get_roster(self, team_slug: str, *, year: int = 2026) -> dict[str, Any]:
        """Fetch roster payload. Returns {ok, players, coach, status_code, error}."""
        if not self.configured:
            return {"ok": False, "players": [], "coach": None, "status_code": 0, "error": "not_configured"}

        path = f"/fifa/worldcup/v1/teams/{quote(team_slug, safe='')}/roster"
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=settings.zafronix_request_timeout) as client:
                response = await client.get(url, headers=self._headers(), params={"year": year})
        except httpx.HTTPError as exc:
            logger.warning("Zafronix roster request failed for %s: %s", team_slug, exc)
            return {"ok": False, "players": [], "coach": None, "status_code": 0, "error": str(exc)}

        if response.status_code == 404:
            return {"ok": False, "players": [], "coach": None, "status_code": 404, "error": "not_found"}

        if response.status_code == 401:
            logger.error("Zafronix API unauthorized - check ZAFRONIX_API_KEY")
            return {"ok": False, "players": [], "coach": None, "status_code": 401, "error": "unauthorized"}

        if response.status_code == 429:
            return {"ok": False, "players": [], "coach": None, "status_code": 429, "error": "rate_limited"}

        if response.status_code >= 400:
            return {
                "ok": False,
                "players": [],
                "coach": None,
                "status_code": response.status_code,
                "error": response.text[:200],
            }

        return _parse_roster_body(response.json())


def _parse_roster_body(body: Any) -> dict[str, Any]:
    coach: str | None = None
    raw_players: list[Any] = []

    if isinstance(body, dict):
        coach = _extract_coach(body)
        raw = body.get("players") or body.get("roster") or body.get("squad")
        if isinstance(raw, list):
            raw_players = raw
    elif isinstance(body, list):
        raw_players = body

    players = [_normalize_player(row) for row in raw_players if isinstance(row, dict)]
    players = [p for p in players if p is not None]

    return {
        "ok": bool(players),
        "players": players,
        "coach": coach,
        "status_code": 200,
        "error": None if players else "empty_roster",
    }


def _extract_coach(payload: dict) -> str | None:
    for key in ("coach", "head_coach", "headCoach", "manager"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            name = value.get("name") or value.get("full_name")
            if name and str(name).strip():
                return str(name).strip()
    return None


def _normalize_player(row: dict) -> dict | None:
    name = row.get("name") or row.get("player") or row.get("full_name")
    if not name or not str(name).strip():
        return None

    raw_position = str(row.get("position") or row.get("pos") or "").upper().strip()
    position = map_zafronix_position(raw_position)

    jersey = row.get("jersey") or row.get("number") or row.get("shirt_number")
    try:
        jersey_num = int(jersey) if jersey is not None else None
    except (TypeError, ValueError):
        jersey_num = None

    club_raw = row.get("club")
    club = _format_club(club_raw)

    display_name, is_captain = _parse_player_name(str(name).strip())

    return {
        "jersey": jersey_num,
        "name": display_name,
        "position": position,
        "raw_position": raw_position or None,
        "club": club,
        "is_captain": is_captain,
    }


def _format_club(club_raw: Any) -> str | None:
    if club_raw is None:
        return None
    if isinstance(club_raw, str):
        return club_raw.strip() or None
    if isinstance(club_raw, dict):
        name = club_raw.get("name") or club_raw.get("club")
        country = club_raw.get("country")
        if name and country:
            return f"{name} ({country})"
        if name:
            return str(name).strip()
    return None
