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
        s = _normalize_quotes(raw.strip())
        # Empty / no-goals markers (incl. empty braces and whitespace-only braces).
        if s.lower() in ("null", "", "[]", "{}", "none") or s.strip("{}[] \t") == "":
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass
        # API often returns {"Name 9'","Name 67'"} with curly quotes (not valid JSON array).
        if s.startswith("{") and s.endswith("}"):
            inner = s[1:-1]
            quoted = re.findall(r'"([^"]+)"', inner) or re.findall(r"'([^']+)'", inner)
            if quoted:
                return quoted
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1]
            quoted = re.findall(r'"([^"]+)"', inner) or re.findall(r"'([^']+)'", inner)
            if quoted:
                return quoted
    return []


def _normalize_quotes(text: str) -> str:
    return (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


# Trailing minute token: "7'", "45'+5'", "90+2", with optional quotes/spaces.
# Captures the base minute and optional stoppage-time addition.
_MINUTE_TOKEN_RE = re.compile(
    r"(?P<minute>\d{1,3})\s*['\u2019]?\s*(?:\+\s*(?P<added>\d{1,2})\s*['\u2019]?)?\s*$"
)

# A trustworthy scorer name: Latin script only (incl. common diacritics) plus
# spaces and . ' - ( ) . The parens allow a kept annotation like "(OG)"/"(pen)".
# Rejects Arabic/Persian/Cyrillic/CJK and other non-Latin text.
_LATIN_NAME_RE = re.compile(
    r"^[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f0-9 .'\u2019()\-]*$"
)

# Trailing "(OG)" / "(pen)" style annotation, kept (Latin only) and re-appended.
_ANNOTATION_RE = re.compile(r"\s*\(([^)]{1,12})\)\s*$")

_MAX_MINUTE = 120
_MAX_ADDED = 30


def is_english_name(name: str) -> bool:
    """True only when the name is non-empty Latin/English script."""
    return bool(name) and bool(_LATIN_NAME_RE.match(name.strip()))


def split_name_minute(item: str) -> tuple[str, int | None, int | None]:
    """Split a scorer token into (name, minute, added).

    Handles stoppage time ("F. Balogun 45'+5'" -> 45, 5) and a trailing own-goal /
    penalty annotation ("D. Bobadilla 7'(OG)" -> "D. Bobadilla (OG)", 7). A token
    with no parseable minute returns (name, None, None).
    """
    text = _normalize_quotes(str(item)).strip().strip('"').strip()

    note: str | None = None
    annotation = _ANNOTATION_RE.search(text)
    if annotation:
        candidate = annotation.group(1).strip()
        # Keep only short Latin annotations (e.g. OG, pen); drop anything else.
        if re.fullmatch(r"[A-Za-z.\s]{1,12}", candidate):
            note = candidate
        text = text[: annotation.start()].strip()

    match = _MINUTE_TOKEN_RE.search(text)
    if not match:
        name = text.strip(" -'\u2019").strip()
        minute = added = None
    else:
        minute = int(match.group("minute"))
        added = int(match.group("added")) if match.group("added") else None
        name = text[: match.start()].strip().strip("-").strip()

    if note and name:
        name = f"{name} ({note})"
    return name, minute, added


def parse_scorers_clean(raw: object) -> list[dict] | None:
    """Live-acceptance parser: every cleanly-parseable scorer, count-tolerant.

    Returns an ordered list of ``{player_name, minute, added_time, raw}`` - which
    may be SHORTER than the score (the API's scorers field often lags), and is
    ``[]`` for a genuine no-scorers payload (the literal "null", ``{}``, empty).
    Returns ``None`` only when the payload is UNTRUSTWORTHY - any entry is
    non-Latin or has an unparseable/out-of-range minute - so callers HOLD the
    last known-good set instead of wiping it. Does NOT gate on count == score;
    that strict check belongs to the reconciler (``parse_scorers``). Never raises.
    """
    try:
        items = parse_scorers_raw(raw)
        out: list[dict] = []
        for item in items:
            if isinstance(item, dict):
                name = str(_first(item, "scorer", "name", "player") or "").strip()
                minute = parse_int(_first(item, "minute", "time", "timestamp", "elapsed"))
                added = parse_int(_first(item, "added_time", "extra", "stoppage"))
                raw_item = str(_first(item, "scorer", "name", "player") or "")
            else:
                name, minute, added = split_name_minute(str(item))
                raw_item = str(item)
            if not is_english_name(name):
                return None
            if minute is None or not (0 <= minute <= _MAX_MINUTE):
                return None
            if added is not None and not (0 <= added <= _MAX_ADDED):
                return None
            out.append(
                {"player_name": name, "minute": minute, "added_time": added, "raw": raw_item}
            )
        return out
    except Exception:
        return None


def parse_scorers(raw: object, expected_count: int) -> list[dict] | None:
    """STRICT reconciler verification: a clean scorer list whose count EXACTLY
    equals ``expected_count`` (the side's score), else ``None``. ``[]`` for a
    genuine 0-goal side.

    Use this ONLY to decide ``reconciled`` (the integrity signal). Live acceptance
    uses ``parse_scorers_clean`` (count-tolerant + monotonic) so a lagging scorers
    field never freezes or wipes the timeline.
    """
    clean = parse_scorers_clean(raw)
    if clean is None:
        return None
    return clean if len(clean) == max(expected_count, 0) else None


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
