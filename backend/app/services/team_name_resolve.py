"""Map KickOff26 team records to Zafronix API slugs and local JSON keys."""

from __future__ import annotations

import unicodedata

from app.models import Team

# Zafronix roster URL slug (path segment) overrides by team code.
ZAFRONIX_SLUG_BY_CODE: dict[str, str] = {
    "CIV": "Cote d'Ivoire",
    "CUW": "Curaçao",
    "TUR": "Turkiye",
    "CZE": "Czech Republic",
    "COD": "Democratic Republic of the Congo",
    "KOR": "South Korea",
}

# Canonical keys in team_coaches_2026.json / players_to_watch_2026.json (by team code).
LOCAL_JSON_KEY_BY_CODE: dict[str, str] = {
    "MEX": "Mexico",
    "RSA": "South Africa",
    "KOR": "South Korea",
    "CZE": "Czechia",
    "CAN": "Canada",
    "BIH": "Bosnia and Herzegovina",
    "QAT": "Qatar",
    "SUI": "Switzerland",
    "BRA": "Brazil",
    "MAR": "Morocco",
    "HAI": "Haiti",
    "SCO": "Scotland",
    "USA": "United States",
    "PAR": "Paraguay",
    "AUS": "Australia",
    "TUR": "Turkiye",
    "GER": "Germany",
    "CUW": "Curacao",
    "CIV": "Cote d'Ivoire",
    "ECU": "Ecuador",
    "NED": "Netherlands",
    "JPN": "Japan",
    "SWE": "Sweden",
    "TUN": "Tunisia",
    "BEL": "Belgium",
    "EGY": "Egypt",
    "IRN": "Iran",
    "NZL": "New Zealand",
    "ESP": "Spain",
    "CPV": "Cape Verde",
    "KSA": "Saudi Arabia",
    "URU": "Uruguay",
    "FRA": "France",
    "IRQ": "Iraq",
    "SEN": "Senegal",
    "NOR": "Norway",
    "ARG": "Argentina",
    "ALG": "Algeria",
    "AUT": "Austria",
    "JOR": "Jordan",
    "POR": "Portugal",
    "COD": "DR Congo",
    "UZB": "Uzbekistan",
    "COL": "Colombia",
    "ENG": "England",
    "CRO": "Croatia",
    "GHA": "Ghana",
    "PAN": "Panama",
}

# Normalized display-name aliases → canonical JSON key (when API name differs from JSON).
NAME_ALIAS_TO_JSON_KEY: dict[str, str] = {
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "turkey": "Turkiye",
    "turkiye": "Turkiye",
    "türkiye": "Turkiye",
    "south korea": "South Korea",
    "korea republic": "South Korea",
    "republic of korea": "South Korea",
    "ivory coast": "Cote d'Ivoire",
    "cote divoire": "Cote d'Ivoire",
    "cote d'ivoire": "Cote d'Ivoire",
    "côte d'ivoire": "Cote d'Ivoire",
    "usa": "United States",
    "united states of america": "United States",
    "dr congo": "DR Congo",
    "congo dr": "DR Congo",
    "democratic republic of the congo": "DR Congo",
    "drc": "DR Congo",
    "curacao": "Curacao",
    "curaçao": "Curacao",
    "bosnia & herzegovina": "Bosnia and Herzegovina",
    "cape verde islands": "Cape Verde",
    "cabo verde": "Cape Verde",
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_lookup_key(name: str) -> str:
    return _strip_accents(name).strip().lower()


def zafronix_slug_for_team(team: Team) -> str:
    if team.code in ZAFRONIX_SLUG_BY_CODE:
        return ZAFRONIX_SLUG_BY_CODE[team.code]
    return team.name


def local_json_key_for_team(team: Team) -> str:
    """Resolve the canonical JSON file key for a team record."""
    if team.code in LOCAL_JSON_KEY_BY_CODE:
        return LOCAL_JSON_KEY_BY_CODE[team.code]
    alias = NAME_ALIAS_TO_JSON_KEY.get(normalize_lookup_key(team.name))
    if alias:
        return alias
    return team.name


def resolve_json_entry_key(team: Team, raw: dict) -> str | None:
    """Find the matching key in a coaches/players JSON dict for this team."""
    if not raw:
        return None

    preferred = local_json_key_for_team(team)
    if preferred in raw:
        return preferred

    index = {normalize_lookup_key(k): k for k in raw if not str(k).startswith("_")}
    canonical = index.get(normalize_lookup_key(preferred))
    if canonical:
        return canonical

    canonical = index.get(normalize_lookup_key(team.name))
    if canonical:
        return canonical

    alias = NAME_ALIAS_TO_JSON_KEY.get(normalize_lookup_key(team.name))
    if alias and alias in raw:
        return alias
    if alias:
        canonical = index.get(normalize_lookup_key(alias))
        if canonical:
            return canonical

    return None
