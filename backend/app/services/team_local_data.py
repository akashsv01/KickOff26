"""Load local coach and player-to-watch JSON (no runtime web fetch)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.models import Team
from app.services.team_name_resolve import resolve_json_entry_key

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
COACHES_PATH = DATA_DIR / "team_coaches_2026.json"
PLAYERS_PATH = DATA_DIR / "players_to_watch_2026.json"


@lru_cache(maxsize=1)
def _load_coaches_raw() -> dict[str, str]:
    if not COACHES_PATH.is_file():
        logger.warning("Missing coaches file: %s", COACHES_PATH)
        return {}
    data = json.loads(COACHES_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, str)}


@lru_cache(maxsize=1)
def _load_players_raw() -> dict[str, dict]:
    if not PLAYERS_PATH.is_file():
        logger.warning("Missing players-to-watch file: %s", PLAYERS_PATH)
        return {}
    data = json.loads(PLAYERS_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}



def coach_from_local_json(team: Team) -> str | None:
    raw = _load_coaches_raw()
    key = resolve_json_entry_key(team, raw)
    return raw.get(key) if key else None


def player_to_watch_from_local_json(team: Team) -> dict | None:
    raw = _load_players_raw()
    key = resolve_json_entry_key(team, raw)
    entry = raw.get(key) if key else None
    if not entry:
        return None
    player = str(entry.get("player") or "").strip()
    reason = str(entry.get("reason") or "").strip()
    image_url = str(entry.get("image_url") or "").strip()
    if not player:
        return None
    return {"player": player, "reason": reason, "image_url": image_url or None}
