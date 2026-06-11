"""Parse rezarahiminia World Cup 2026 API payloads (string quirks, dual IDs).

Each record exposes two identifiers:
  _id  - MongoDB object id (used in GET /get/game/{_id}, /get/team/{_id})
  id   - sequential string id (used in relational refs: home_team_id, stadium_id, …)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.models import MatchStatus
from app.services.match_calendar import SCHEDULE_CALENDAR_TZ
from app.services.openfootball import GROUND_IANA, NAME_TO_CODE

# Map API city_en values to our HOST_CITIES keys / IANA zones.
_CITY_IANA: dict[str, str] = {
    "Mexico City": "America/Mexico_City",
    "Guadalajara": "America/Mexico_City",
    "Monterrey": "America/Monterrey",
    "Toronto": "America/Toronto",
    "Vancouver": "America/Vancouver",
    "Los Angeles": "America/Los_Angeles",
    "San Francisco": "America/Los_Angeles",
    "Seattle": "America/Los_Angeles",
    "Boston": "America/New_York",
    "New York": "America/New_York",
    "Philadelphia": "America/New_York",
    "Miami": "America/New_York",
    "Atlanta": "America/New_York",
    "Houston": "America/Chicago",
    "Dallas": "America/Chicago",
    "Kansas City": "America/Chicago",
}


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return None


def api_object_id(record: dict) -> str | None:
    oid = _first(record, "_id", "object_id", "objectId")
    return str(oid).strip() if oid else None


def api_seq_id(record: dict) -> str | None:
    sid = _first(record, "id", "seq_id", "seqId")
    return str(sid).strip() if sid is not None and str(sid).strip() else None


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().lower()
    if s in ("", "null", "none"):
        return None
    digits = re.findall(r"\d+", s)
    return int(digits[0]) if digits else None


def parse_finished(value: Any) -> bool:
    """finished field is the string \"TRUE\" / \"FALSE\" - never use bare bool()."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    s = str(value).strip().upper()
    if s in ("FALSE", "0", "NO", "NS", "NOTSTARTED", "NULL", "NONE", ""):
        return False
    return s in ("TRUE", "1", "YES", "FT", "FINISHED", "DONE")


def parse_elapsed_minute(elapsed: Any) -> int | None:
    if elapsed is None:
        return None
    s = str(elapsed).strip().lower()
    if s in ("", "notstarted", "ns", "null", "none", "-", "scheduled", "finished", "live"):
        return None
    if s in ("ht", "halftime", "half"):
        return 45
    return parse_int(elapsed)


def derive_status(game: dict) -> MatchStatus:
    """Derive status from finished + time_elapsed (\"notstarted\" | \"live\" | \"finished\" | minutes)."""
    if parse_finished(_first(game, "finished", "is_finished", "completed")):
        return MatchStatus.FINISHED
    elapsed_raw = str(_first(game, "time_elapsed", "timeElapsed", "elapsed") or "").strip().lower()
    if elapsed_raw == "finished":
        return MatchStatus.FINISHED
    if elapsed_raw == "live":
        return MatchStatus.LIVE
    minute = parse_elapsed_minute(elapsed_raw)
    if minute is not None:
        return MatchStatus.LIVE
    return MatchStatus.SCHEDULED


def normalize_code(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "tbd"):
        return None
    if text in NAME_TO_CODE:
        return NAME_TO_CODE[text]
    if len(text) <= 4 and text.isalpha():
        return text.upper()
    return None


def parse_scorers_raw(raw: Any) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if s.lower() in ("null", "", "[]", "none"):
            return []
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def parse_scorer_events(game: dict) -> list[dict]:
    out: list[dict] = []
    for side, key in (("home", "home_scorers"), ("away", "away_scorers")):
        for entry in parse_scorers_raw(_first(game, key, f"{side}Scorers")):
            if isinstance(entry, dict):
                player = _first(entry, "scorer", "name", "player") or "Unknown player"
                minute = parse_int(_first(entry, "minute", "time", "timestamp", "elapsed")) or 0
            else:
                player = str(entry)
                minute = 0
            out.append(
                {"type": "goal", "minute": minute, "team": side, "player": str(player).strip()}
            )
    return out


def parse_local_date(
    value: str | None,
    *,
    city_en: str | None = None,
) -> tuple[datetime | None, str | None]:
    """Parse API local_date \"MM/DD/YYYY HH:mm\" → (UTC kickoff, Eastern calendar date)."""
    if not value or str(value).strip().lower() in ("null", "none", ""):
        return None, None
    text = str(value).strip()
    try:
        naive = datetime.strptime(text, "%m/%d/%Y %H:%M")
    except ValueError:
        return None, None

    iana = _CITY_IANA.get(city_en or "", "America/New_York")
    if city_en:
        for ground, tz in GROUND_IANA.items():
            if city_en.lower() in ground.lower():
                iana = tz
                break
    local = naive.replace(tzinfo=ZoneInfo(iana))
    kickoff_utc = local.astimezone(timezone.utc)
    calendar_date = kickoff_utc.astimezone(SCHEDULE_CALENDAR_TZ).date().isoformat()
    return kickoff_utc, calendar_date


def map_stage(api_type: str | None) -> str:
    t = (api_type or "group").strip().lower()
    if t == "group":
        return "group"
    mapping = {
        "r32": "r32",
        "round of 32": "r32",
        "r16": "r16",
        "round of 16": "r16",
        "qf": "qf",
        "quarter": "qf",
        "quarter-final": "qf",
        "sf": "sf",
        "semi": "sf",
        "semi-final": "sf",
        "final": "final",
        "third": "third",
    }
    for key, stage in mapping.items():
        if key in t:
            return stage
    return t or "group"
