"""Load real 2026 tournament fixtures from cached openfootball/worldcup.json."""



from __future__ import annotations



from app.services.match_calendar import summarize_match_days

from app.services.openfootball import (
    ensure_worldcup_cache,
    get_tournament_window,
    opening_match_external_id as _opening_match_external_id,
    parse_fixtures,
)

from app.services.tournament_2026 import OFFICIAL_TEAMS





def get_fixtures_seed() -> list[dict]:

    """Return normalized fixture dicts ready for DB upsert."""

    ensure_worldcup_cache()

    return parse_fixtures()





def get_tournament_window_meta() -> dict:

    return get_tournament_window()





def get_official_group_map() -> dict[str, str]:

    return {t["code"]: t["group"] for t in OFFICIAL_TEAMS}





def get_all_team_defs() -> list[dict]:

    """Official 48 teams (confirmed draw) + knockout placeholder teams from fixtures."""

    official_codes = {t["code"] for t in OFFICIAL_TEAMS}

    teams = list(OFFICIAL_TEAMS)

    seen = set(official_codes)



    for f in get_fixtures_seed():

        for code, name in (

            (f["home_code"], f["home_name"]),

            (f["away_code"], f["away_name"]),

        ):

            if code in seen:

                continue

            seen.add(code)

            teams.append(

                {

                    "code": code,

                    "name": name,

                    "group": None,

                    "elo": 1500,

                    "placeholder": True,

                }

            )

    return teams





def get_match_days_summary() -> list[dict]:

    """Venue-local dates with fixture counts for calendar."""

    return summarize_match_days(get_fixtures_seed())





def opening_match_id() -> str:
    return _opening_match_external_id()


def opening_match_external_id() -> str:
    return _opening_match_external_id()


