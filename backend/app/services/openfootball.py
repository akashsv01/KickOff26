"""Load the real 2026 World Cup schedule from openfootball/worldcup.json.

Source: https://github.com/openfootball/worldcup.json
Cached locally at backend/data/worldcup_2026.json for offline use after first fetch.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OFFICIAL_EXTERNAL_PREFIX = "wc2026-m"
OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
)
CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "worldcup_2026.json"

NAME_TO_CODE: dict[str, str] = {
    "Mexico": "MEX",
    "South Africa": "RSA",
    "South Korea": "KOR",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "Canada": "CAN",
    "Bosnia & Herzegovina": "BIH",
    "Bosnia and Herzegovina": "BIH",
    "Qatar": "QAT",
    "Switzerland": "SUI",
    "Brazil": "BRA",
    "Morocco": "MAR",
    "Haiti": "HAI",
    "Scotland": "SCO",
    "USA": "USA",
    "United States": "USA",
    "Paraguay": "PAR",
    "Australia": "AUS",
    "Turkey": "TUR",
    "Türkiye": "TUR",
    "Germany": "GER",
    "Curaçao": "CUW",
    "Curacao": "CUW",
    "Ivory Coast": "CIV",
    "Côte d'Ivoire": "CIV",
    "Ecuador": "ECU",
    "Netherlands": "NED",
    "Japan": "JPN",
    "Sweden": "SWE",
    "Tunisia": "TUN",
    "Belgium": "BEL",
    "Egypt": "EGY",
    "Iran": "IRN",
    "New Zealand": "NZL",
    "Spain": "ESP",
    "Cape Verde": "CPV",
    "Saudi Arabia": "KSA",
    "Uruguay": "URU",
    "France": "FRA",
    "Iraq": "IRQ",
    "Norway": "NOR",
    "Senegal": "SEN",
    "Argentina": "ARG",
    "Algeria": "ALG",
    "Austria": "AUT",
    "Jordan": "JOR",
    "Portugal": "POR",
    "DR Congo": "COD",
    "Uzbekistan": "UZB",
    "Colombia": "COL",
    "England": "ENG",
    "Croatia": "CRO",
    "Ghana": "GHA",
    "Panama": "PAN",
}

GROUND_MAP: dict[str, tuple[str, str, str]] = {
    "Mexico City": ("Mexico City", "Estadio Azteca", "Mexico"),
    "Guadalajara (Zapopan)": ("Guadalajara", "Estadio Akron", "Mexico"),
    "Monterrey (Guadalupe)": ("Monterrey", "Estadio BBVA", "Mexico"),
    "Toronto": ("Toronto", "BMO Field", "Canada"),
    "Vancouver": ("Vancouver", "BC Place", "Canada"),
    "Los Angeles (Inglewood)": ("Los Angeles", "SoFi Stadium", "USA"),
    "San Francisco Bay Area (Santa Clara)": ("San Francisco", "Levi's Stadium", "USA"),
    "Seattle": ("Seattle", "Lumen Field", "USA"),
    "Boston (Foxborough)": ("Boston", "Gillette Stadium", "USA"),
    "New York/New Jersey (East Rutherford)": ("New York", "MetLife Stadium", "USA"),
    "Philadelphia": ("Philadelphia", "Lincoln Financial Field", "USA"),
    "Miami (Miami Gardens)": ("Miami", "Hard Rock Stadium", "USA"),
    "Atlanta": ("Atlanta", "Mercedes-Benz Stadium", "USA"),
    "Houston": ("Houston", "NRG Stadium", "USA"),
    "Dallas (Arlington)": ("Dallas", "AT&T Stadium", "USA"),
    "Kansas City": ("Kansas City", "Arrowhead Stadium", "USA"),
}

GROUND_IANA: dict[str, str] = {
    "Mexico City": "America/Mexico_City",
    "Guadalajara (Zapopan)": "America/Mexico_City",
    "Monterrey (Guadalupe)": "America/Monterrey",
    "Toronto": "America/Toronto",
    "Vancouver": "America/Vancouver",
    "Los Angeles (Inglewood)": "America/Los_Angeles",
    "San Francisco Bay Area (Santa Clara)": "America/Los_Angeles",
    "Seattle": "America/Los_Angeles",
    "Boston (Foxborough)": "America/New_York",
    "New York/New Jersey (East Rutherford)": "America/New_York",
    "Philadelphia": "America/New_York",
    "Miami (Miami Gardens)": "America/New_York",
    "Atlanta": "America/New_York",
    "Houston": "America/Chicago",
    "Dallas (Arlington)": "America/Chicago",
    "Kansas City": "America/Chicago",
}

STAGE_MAP: dict[str, str] = {
    "Round of 32": "r32",
    "Round of 16": "r16",
    "Quarter-final": "qf",
    "Semi-final": "sf",
    "Match for third place": "third",
    "Final": "final",
}

from app.services.match_calendar import SCHEDULE_CALENDAR_TZ

DEMO_LIVE_HOME = "MEX"
DEMO_LIVE_AWAY = "RSA"


def team_code(name: str) -> str:
    if name in NAME_TO_CODE:
        return NAME_TO_CODE[name]
    return re.sub(r"[^A-Z0-9]", "", name.upper())[:8] or "TBD"


def parse_kickoff(date_str: str, time_str: str, ground: str) -> tuple[str, datetime, str]:
    """Return (local_date YYYY-MM-DD, kickoff UTC datetime, IANA timezone)."""
    local_date = date_str
    iana = GROUND_IANA.get(ground, "America/New_York")
    m = re.match(r"(\d{2}):(\d{2})\s+UTC([+-]\d+)", (time_str or "").strip())
    if not m:
        fallback = datetime.fromisoformat(f"{date_str}T18:00:00").replace(tzinfo=ZoneInfo(iana))
        return local_date, fallback.astimezone(timezone.utc), iana

    hh, mm, offset = int(m.group(1)), int(m.group(2)), int(m.group(3))
    fixed_tz = timezone(timedelta(hours=offset))
    local_dt = datetime(
        int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10]), hh, mm, tzinfo=fixed_tz
    )
    return local_date, local_dt.astimezone(timezone.utc), iana


def fetch_remote() -> dict:
    with urllib.request.urlopen(OPENFOOTBALL_URL, timeout=30) as resp:
        return json.load(resp)


def ensure_worldcup_cache(*, force: bool = False) -> Path:
    """Fetch openfootball JSON if cache missing (or force refresh)."""
    if CACHE_PATH.exists() and not force:
        return CACHE_PATH
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_remote()
    CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return CACHE_PATH


def load_raw() -> dict:
    ensure_worldcup_cache()
    with CACHE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def parse_fixtures(raw: dict | None = None) -> list[dict]:
    """Parse openfootball matches into normalized fixture dicts for DB seeding."""
    from app.services.tournament_2026 import HOST_CITIES

    source = raw if raw is not None else load_raw()
    fixtures: list[dict] = []

    for i, m in enumerate(source["matches"], start=1):
        mid = m.get("num", i)
        group_raw = m.get("group", "")
        group = group_raw.replace("Group ", "").strip() if group_raw.startswith("Group") else None
        rnd = m.get("round", "")
        stage = STAGE_MAP.get(rnd, "group")
        ground = m["ground"]
        city, stadium, country = GROUND_MAP.get(ground, (ground, ground, "USA"))
        home = team_code(m["team1"])
        away = team_code(m["team2"])
        local_date, kickoff_at, iana_tz = parse_kickoff(m["date"], m.get("time", ""), ground)
        # Official 2026 schedule PDF buckets by Eastern Time calendar day.
        calendar_date = kickoff_at.astimezone(SCHEDULE_CALENDAR_TZ).date().isoformat()
        info = HOST_CITIES.get(city, {})

        fixtures.append(
            {
                "match_id": mid,
                "external_id": f"wc2026-m{mid:03d}",
                "home_code": home,
                "away_code": away,
                "home_name": m["team1"],
                "away_name": m["team2"],
                "group": group,
                "stage": stage,
                "round_label": rnd,
                "kickoff_at": kickoff_at,
                "local_date": calendar_date,
                "timezone": "America/New_York",
                "venue_timezone": iana_tz,
                "city": city,
                "country": country if country else info.get("country", "USA"),
                "venue": stadium if stadium else info.get("stadium", city),
                "lat": info.get("lat", 0.0),
                "lng": info.get("lng", 0.0),
                "ticket_usd": info.get("ticket_usd", 150),
                "status": "SCHEDULED",
            }
        )

    return fixtures


def get_tournament_window(fixtures: list[dict] | None = None) -> dict[str, str]:
    items = fixtures if fixtures is not None else parse_fixtures()
    dates = sorted(f["local_date"] for f in items if f.get("local_date"))
    if not dates:
        return {"start": "2026-06-11", "end": "2026-07-19"}
    return {"start": dates[0], "end": dates[-1]}


def opening_match_external_id(fixtures: list[dict] | None = None) -> str:
    items = fixtures if fixtures is not None else parse_fixtures()
    for f in items:
        if f["home_code"] == DEMO_LIVE_HOME and f["away_code"] == DEMO_LIVE_AWAY:
            return f["external_id"]
    return items[0]["external_id"] if items else "wc2026-m001"
