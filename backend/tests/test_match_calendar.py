"""Calendar bucketing: badge counts must match rendered day lists."""



import pytest

from httpx import AsyncClient



from app.services.fixtures_loader import get_fixtures_seed, get_match_days_summary

from app.services.match_calendar import match_calendar_date, matches_on_date, summarize_match_days





def test_fixtures_have_72_group_matches():

    seed = get_fixtures_seed()

    group = [f for f in seed if f.get("stage") == "group"]

    assert len(group) == 72

    from collections import Counter

    counts = Counter(f["group"] for f in group)
    assert len(counts) == 12
    assert all(v == 6 for v in counts.values())
    assert len(seed) == 104


def test_openfootball_team_name_mapping():
    from app.services.openfootball import team_code

    assert team_code("Czech Republic") == "CZE"
    assert team_code("Czechia") == "CZE"
    assert team_code("Bosnia & Herzegovina") == "BIH"
    assert team_code("Côte d'Ivoire") == "CIV"
    assert team_code("South Korea") == "KOR"


def test_demo_live_match_is_mexico_south_africa():
    from app.services.fixtures_loader import opening_match_id

    seed = get_fixtures_seed()
    opening = next(f for f in seed if f["external_id"] == opening_match_id())
    assert opening["home_code"] == "MEX"
    assert opening["away_code"] == "RSA"


def test_confirmed_draw_groups_in_fixtures():
    seed = get_fixtures_seed()
    group_teams: dict[str, set[str]] = {}
    for f in seed:
        if f.get("stage") != "group" or not f.get("group"):
            continue
        g = f["group"]
        group_teams.setdefault(g, set()).update([f["home_code"], f["away_code"]])
    assert group_teams["A"] == {"MEX", "KOR", "RSA", "CZE"}
    assert group_teams["B"] == {"CAN", "SUI", "QAT", "BIH"}
    assert group_teams["D"] == {"USA", "PAR", "AUS", "TUR"}
    assert group_teams["C"] == {"BRA", "MAR", "SCO", "HAI"}





def test_late_kickoff_buckets_by_eastern_calendar_date():
    seed = get_fixtures_seed()
    kor_cze = next(f for f in seed if f["home_code"] == "KOR" and f["away_code"] == "CZE")
    assert kor_cze["local_date"] == "2026-06-11"
    assert str(kor_cze["kickoff_at"]).startswith("2026-06-12")





def test_day_summary_matches_per_date_fixture_counts():

    seed = get_fixtures_seed()

    days = get_match_days_summary()

    for day in days:

        rendered = matches_on_date(seed, day["date"])

        assert len(rendered) == day["match_count"], f"Mismatch on {day['date']}"





def test_summarize_matches_same_as_fixture_summary():

    seed = get_fixtures_seed()

    assert summarize_match_days(seed) == get_match_days_summary()





@pytest.mark.asyncio

async def test_api_day_badges_match_rendered_lists(client: AsyncClient):

    days = (await client.get("/api/matchday/days")).json()

    matches = (await client.get("/api/matchday/matches")).json()

    assert len(days) > 0

    for day in days:

        on_day = [m for m in matches if m.get("local_date") == day["date"]]

        assert len(on_day) == day["match_count"], (

            f"{day['date']}: badge {day['match_count']} vs list {len(on_day)}"

        )





def test_match_calendar_date_prefers_local_date():

    assert match_calendar_date({"local_date": "2026-06-11", "kickoff_at": "2026-06-12T02:00:00+00:00"}) == "2026-06-11"


