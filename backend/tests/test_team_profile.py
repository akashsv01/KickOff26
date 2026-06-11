from unittest.mock import AsyncMock, patch

import pytest

from app.models import Team, TeamRoster
from app.services.team_local_data import coach_from_local_json, player_to_watch_from_local_json
from app.services.team_name_resolve import zafronix_slug_for_team, normalize_lookup_key
from app.services.team_roster_service import (
    group_players_by_position,
    players_need_raw_position_refresh,
    resolve_coach,
    resolve_group_position,
)


def _team(**kwargs) -> Team:
    defaults = dict(id=1, name="Mexico", code="MEX", group_letter="A", elo_rating=1800.0)
    defaults.update(kwargs)
    return Team(**defaults)


def test_zafronix_slug_overrides():
    assert zafronix_slug_for_team(_team(code="CIV", name="Côte d'Ivoire")) == "Cote d'Ivoire"
    assert zafronix_slug_for_team(_team(code="CUW", name="Curaçao")) == "Curaçao"
    assert zafronix_slug_for_team(_team(code="KOR", name="Korea Republic")) == "Korea Republic"


def test_normalize_lookup_key_strips_accents():
    assert normalize_lookup_key("Côte d'Ivoire") == normalize_lookup_key("Cote d'Ivoire")


def test_local_coach_and_player_to_watch_mexico():
    team = _team()
    assert coach_from_local_json(team) == "Javier Aguirre"
    ptw = player_to_watch_from_local_json(team)
    assert ptw is not None
    assert ptw["player"] == "Santiago Gimenez"
    assert ptw["image_url"] is None


def test_local_coach_usa_key_variant():
    team = _team(name="United States", code="USA")
    assert coach_from_local_json(team) == "Mauricio Pochettino"


def test_local_coach_czech_republic_api_name():
    team = _team(name="Czech Republic", code="CZE")
    assert coach_from_local_json(team) == "Miroslav Koubek"
    ptw = player_to_watch_from_local_json(team)
    assert ptw is not None
    assert ptw["player"] == "Patrik Schick"


def test_all_official_teams_resolve_coach_and_player():
    from app.services.tournament_2026 import OFFICIAL_TEAMS

    missing = []
    for entry in OFFICIAL_TEAMS:
        team = _team(name=entry["name"], code=entry["code"], group_letter=entry["group"])
        if not coach_from_local_json(team):
            missing.append(f"{entry['code']} coach")
        if not player_to_watch_from_local_json(team):
            missing.append(f"{entry['code']} player")
    assert missing == [], f"Missing local JSON data: {missing}"


def test_resolve_group_position_prefers_raw_position():
    stale = {"name": "Messi", "position": "MID", "raw_position": "FW"}
    assert resolve_group_position(stale) == "FWD"


def test_players_need_raw_position_refresh():
    assert players_need_raw_position_refresh([{"name": "A", "position": "GK"}]) is True
    assert players_need_raw_position_refresh([{"name": "A", "position": "GK", "raw_position": "GK"}]) is False
    assert players_need_raw_position_refresh([]) is False


def test_group_players_by_position():
    players = [
        {"jersey": 9, "name": "Striker", "position": "FWD", "club": "A"},
        {"jersey": 10, "name": "Messi", "position": "FWD", "club": "MIA"},
        {"jersey": 1, "name": "Keeper", "position": "GK", "club": "B"},
        {"jersey": 5, "name": "Defender", "position": "DEF", "club": "C"},
        {"jersey": 8, "name": "Mid", "position": "MID", "club": "D"},
    ]
    grouped = group_players_by_position(players)
    assert [p["name"] for p in grouped["GK"]] == ["Keeper"]
    assert [p["name"] for p in grouped["FWD"]] == ["Striker", "Messi"]
    assert [p["name"] for p in grouped["MID"]] == ["Mid"]


def test_group_players_splits_forwards_from_stale_mid_bucket_via_raw():
    players = [
        {"jersey": 10, "name": "Lionel Messi", "position": "MID", "raw_position": "FW", "club": "MIA"},
        {"jersey": 20, "name": "Lautaro Martínez", "position": "MID", "raw_position": "FW", "club": "INT"},
        {"jersey": 8, "name": "Midfielder", "position": "MID", "raw_position": "MF", "club": "X"},
    ]
    grouped = group_players_by_position(players)
    assert [p["name"] for p in grouped["FWD"]] == ["Lionel Messi", "Lautaro Martínez"]
    assert [p["name"] for p in grouped["MID"]] == ["Midfielder"]


def test_resolve_coach_prefers_zafronix():
    team = _team()
    row = TeamRoster(team_id=1, coach="API Coach")
    assert resolve_coach(team, row) == ("API Coach", "zafronix")


def test_resolve_coach_falls_back_to_local():
    team = _team()
    assert resolve_coach(team, None) == ("Javier Aguirre", "local")


@pytest.mark.asyncio
async def test_team_profile_endpoint(client, setup_db):
    teams = (await client.get("/api/teams")).json()
    mexico = next(t for t in teams if t["code"] == "MEX")

    mock_players = [
        {"jersey": 1, "name": "Memo Ochoa", "position": "GK", "club": "Club América (Mexico)"},
    ]

    with patch(
        "app.services.team_roster_service.ZafronixApiClient.get_roster",
        new_callable=AsyncMock,
        return_value={"ok": True, "players": mock_players, "coach": None, "status_code": 200},
    ):
        res = await client.get(f"/api/teams/{mexico['id']}/profile")

    assert res.status_code == 200
    body = res.json()
    assert body["coach_display"] == "Javier Aguirre"
    assert body["coach_source"] == "local"
    assert body["player_to_watch"]["player"] == "Santiago Gimenez"
    assert body["squad"]["status"] == "ready"
    assert body["squad"]["players_by_position"]["GK"][0]["name"] == "Memo Ochoa"


@pytest.mark.asyncio
async def test_team_profile_unavailable_when_empty_roster(client, setup_db):
    teams = (await client.get("/api/teams")).json()
    team = teams[0]

    with patch(
        "app.services.team_roster_service.ZafronixApiClient.get_roster",
        new_callable=AsyncMock,
        return_value={"ok": False, "players": [], "coach": None, "status_code": 404, "error": "not_found"},
    ):
        res = await client.get(f"/api/teams/{team['id']}/profile")

    assert res.status_code == 200
    assert res.json()["squad"]["status"] == "unavailable"
