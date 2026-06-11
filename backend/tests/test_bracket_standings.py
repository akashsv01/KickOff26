"""Tests for result-driven group standings and bracket persistence."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.bracket_standings import (
    apply_match_result,
    build_r32_slot_teams,
    compute_group_standings,
    rank_third_placed,
)


def _team(code: str, name: str | None = None) -> dict:
    return {"id": 1, "code": code, "name": name or code}


def test_group_a_loser_ranks_below_unplayed_on_equal_points():
    """Mexico 2-0 South Africa: RSA (-2 GD) must be 4th, below KOR/CZE at 0 GD."""
    teams = [
        _team("MEX", "Mexico"),
        _team("RSA", "South Africa"),
        _team("KOR", "South Korea"),
        _team("CZE", "Czech Republic"),
    ]
    fixtures = [
        {"id": 1, "home": {"code": "MEX"}, "away": {"code": "RSA"}},
        {"id": 2, "home": {"code": "KOR"}, "away": {"code": "CZE"}},
    ]
    results = {1: {"home_score": 2, "away_score": 0}}
    rows = compute_group_standings(teams, fixtures, results)
    codes = [r["code"] for r in rows]

    assert codes[0] == "MEX"
    assert codes[1] == "CZE"
    assert codes[2] == "KOR"
    assert codes[3] == "RSA"
    assert rows[0]["points"] == 3
    assert rows[0]["gd"] == 2
    assert rows[3]["points"] == 0
    assert rows[3]["gd"] == -2
    assert rows[3]["lost"] == 1


def test_standings_points_and_tiebreaker_gd():
    teams = [_team("AAA"), _team("BBB"), _team("CCC"), _team("DDD")]
    fixtures = [
        {"id": 1, "home": {"code": "AAA"}, "away": {"code": "BBB"}},
        {"id": 2, "home": {"code": "CCC"}, "away": {"code": "DDD"}},
        {"id": 3, "home": {"code": "AAA"}, "away": {"code": "CCC"}},
        {"id": 4, "home": {"code": "BBB"}, "away": {"code": "DDD"}},
    ]
    results = {
        1: {"home_score": 2, "away_score": 0},
        2: {"home_score": 1, "away_score": 1},
        3: {"home_score": 1, "away_score": 1},
        4: {"home_score": 0, "away_score": 1},
    }
    rows = compute_group_standings(teams, fixtures, results)
    by_code = {r["code"]: r for r in rows}

    assert by_code["AAA"]["points"] == 4
    assert by_code["AAA"]["won"] == 1
    assert by_code["AAA"]["drawn"] == 1
    assert by_code["DDD"]["points"] == 4
    assert by_code["DDD"]["gd"] == 1
    assert by_code["AAA"]["gd"] == 2
    assert rows[0]["code"] == "AAA"
    assert rows[1]["code"] == "DDD"


def test_apply_match_result_draw_gives_one_point_each():
    home = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "points": 0}
    away = dict(home)
    apply_match_result(home, away, 2, 2)
    assert home["points"] == 1
    assert away["points"] == 1
    assert home["drawn"] == 1


def test_rank_third_placed_by_points():
    standings = {
        "A": [
            {"code": "A1", "points": 9, "gd": 3, "gf": 5, "rank": 1},
            {"code": "A2", "points": 6, "gd": 1, "gf": 4, "rank": 2},
            {"code": "A3", "points": 4, "gd": 0, "gf": 3, "rank": 3},
            {"code": "A4", "points": 0, "gd": -4, "gf": 1, "rank": 4},
        ],
        "B": [
            {"code": "B1", "points": 7, "gd": 2, "gf": 4, "rank": 1},
            {"code": "B2", "points": 5, "gd": 0, "gf": 3, "rank": 2},
            {"code": "B3", "points": 4, "gd": 1, "gf": 2, "rank": 3},
            {"code": "B4", "points": 1, "gd": -3, "gf": 1, "rank": 4},
        ],
    }
    ranked = rank_third_placed(standings)
    assert ranked[0] == "B3"
    assert ranked[1] == "A3"


def test_build_r32_slot_teams_maps_sixteen_matches():
    pairings = [("A1", "B3"), ("C1", "D3")] + [("X", "Y")] * 14
    slots = build_r32_slot_teams(pairings[:16])
    assert slots["r32-1:a"] == "A1"
    assert slots["r32-1:b"] == "B3"
    assert slots["r32-16:a"] == pairings[15][0]


@pytest.mark.asyncio
async def test_save_reload_restores_picks(auth_client: AsyncClient):
    payload = {
        "name": "Test Bracket",
        "picks": {
            "version": 2,
            "group_results": {"101": {"home_score": 2, "away_score": 1}},
            "knockout": {"r32-1": "BRA"},
            "slot_teams": {"r32-1:a": "BRA", "r32-1:b": "MAR"},
        },
    }
    save_res = await auth_client.post("/api/bracket/save", json=payload)
    assert save_res.status_code == 200

    load_res = await auth_client.get("/api/bracket/picks")
    assert load_res.status_code == 200
    data = load_res.json()
    assert data["picks"]["group_results"]["101"]["home_score"] == 2
    assert data["picks"]["knockout"]["r32-1"] == "BRA"
    assert data["updated_at"] is not None

    save_again = await auth_client.post("/api/bracket/save", json=payload)
    assert save_again.status_code == 200
    assert save_again.json()["id"] == save_res.json()["id"]


@pytest.mark.asyncio
async def test_clear_then_reload_is_empty(auth_client: AsyncClient):
    await auth_client.post(
        "/api/bracket/save",
        json={
            "name": "To Clear",
            "picks": {"group_results": {"1": {"home_score": 1, "away_score": 0}}},
        },
    )
    clear_res = await auth_client.delete("/api/bracket/picks")
    assert clear_res.status_code == 200
    assert clear_res.json()["deleted"] >= 1

    load_res = await auth_client.get("/api/bracket/picks")
    assert load_res.status_code == 200
    assert load_res.json()["picks"] == {}


@pytest.mark.asyncio
async def test_clear_knockout_preserves_group_results(auth_client: AsyncClient):
    await auth_client.post(
        "/api/bracket/save",
        json={
            "name": "Scoped",
            "picks": {
                "group_results": {"101": {"home_score": 2, "away_score": 1}},
                "knockout": {"r32-1": "BRA", "final-1": "BRA"},
            },
        },
    )

    clear_res = await auth_client.delete("/api/bracket/picks/knockout")
    assert clear_res.status_code == 200
    assert clear_res.json()["cleared"] == "knockout"
    assert clear_res.json()["remaining"] is True

    load_res = await auth_client.get("/api/bracket/picks")
    picks = load_res.json()["picks"]
    assert picks.get("group_results") == {"101": {"home_score": 2, "away_score": 1}}
    assert "knockout" not in picks


@pytest.mark.asyncio
async def test_clear_groups_preserves_knockout(auth_client: AsyncClient):
    await auth_client.post(
        "/api/bracket/save",
        json={
            "name": "Scoped",
            "picks": {
                "group_results": {"101": {"home_score": 2, "away_score": 1}},
                "knockout": {"r32-1": "BRA"},
            },
        },
    )

    clear_res = await auth_client.delete("/api/bracket/picks/groups")
    assert clear_res.status_code == 200
    assert clear_res.json()["cleared"] == "groups"
    assert clear_res.json()["remaining"] is True

    load_res = await auth_client.get("/api/bracket/picks")
    picks = load_res.json()["picks"]
    assert picks.get("knockout") == {"r32-1": "BRA"}
    assert "group_results" not in picks


@pytest.mark.asyncio
async def test_scoped_saves_merge_without_overwriting(auth_client: AsyncClient):
    await auth_client.post(
        "/api/bracket/save/groups",
        json={
            "name": "Merge",
            "picks": {
                "version": 2,
                "group_results": {"1": {"home_score": 1, "away_score": 0}},
            },
        },
    )
    await auth_client.post(
        "/api/bracket/save/knockout",
        json={
            "name": "Merge",
            "picks": {"version": 2, "knockout": {"r32-1": "ARG"}},
        },
    )

    load_res = await auth_client.get("/api/bracket/picks")
    picks = load_res.json()["picks"]
    assert picks["group_results"] == {"1": {"home_score": 1, "away_score": 0}}
    assert picks["knockout"] == {"r32-1": "ARG"}

    await auth_client.post(
        "/api/bracket/save/knockout",
        json={
            "name": "Merge",
            "picks": {"version": 2, "knockout": {"r32-1": "BRA", "final-1": "BRA"}},
        },
    )
    load_res = await auth_client.get("/api/bracket/picks")
    picks = load_res.json()["picks"]
    assert picks["group_results"] == {"1": {"home_score": 1, "away_score": 0}}
    assert picks["knockout"]["final-1"] == "BRA"
