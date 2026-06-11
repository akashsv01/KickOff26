import pytest

from app.services.simulator import (
    GroupStanding,
    _simulate_group_stage,
    rank_third_placed,
    run_monte_carlo,
    run_single_simulation,
    _standing_key,
)
import numpy as np


def test_standing_key_orders_by_points():
    a = GroupStanding("A", points=6, gf=5, ga=1)
    b = GroupStanding("B", points=3, gf=3, ga=3)
    assert _standing_key(a) > _standing_key(b)


def test_group_stage_produces_standings():
    rng = np.random.default_rng(42)
    standings = _simulate_group_stage(rng)
    assert len(standings) == 12
    for group, teams in standings.items():
        assert len(teams) == 4
        assert teams[0].points >= teams[1].points


def test_third_place_ranking_selects_eight():
    rng = np.random.default_rng(42)
    standings = _simulate_group_stage(rng)
    third = rank_third_placed(standings)
    assert len(third) == 8


def test_third_place_ranking_by_points():
    standings = {
        "A": [
            GroupStanding("A1", points=9, gf=6, ga=1),
            GroupStanding("A2", points=6, gf=4, ga=2),
            GroupStanding("A3", points=4, gf=3, ga=3),
            GroupStanding("A4", points=0, gf=0, ga=7),
        ],
        "B": [
            GroupStanding("B1", points=7, gf=5, ga=2),
            GroupStanding("B2", points=5, gf=3, ga=3),
            GroupStanding("B3", points=3, gf=2, ga=4),
            GroupStanding("B4", points=1, gf=1, ga=2),
        ],
    }
    for g in "CDEFGHIJKL":
        standings[g] = [
            GroupStanding(f"{g}1", points=6, gf=4, ga=2),
            GroupStanding(f"{g}2", points=4, gf=3, ga=3),
            GroupStanding(f"{g}3", points=2, gf=1, ga=4),
            GroupStanding(f"{g}4", points=0, gf=0, ga=5),
        ]
    third = rank_third_placed(standings)
    assert len(third) == 8
    assert "A3" in third  # 4 pts - should qualify


def test_single_simulation_returns_champion():
    rng = np.random.default_rng(99)
    champion, bracket = run_single_simulation(rng)
    assert champion is not None
    assert "champion" in bracket
    assert bracket["champion"] == champion


def test_monte_carlo_small():
    result = run_monte_carlo(100, seed=42)
    assert result["iterations"] == 100
    assert "champion" in result["team_stats"]
    champ_probs = result["team_stats"]["champion"]
    assert abs(sum(champ_probs.values()) - 100) < 5  # roughly sums to 100%


def test_sanitize_ensures_path_from_bracket():
    from app.services.simulator import sanitize_sim_result

    raw = run_monte_carlo(200, seed=1)
    raw["most_likely_path"] = {}
    fixed = sanitize_sim_result(raw)
    top = next(iter(fixed["team_stats"]["champion"]))
    assert fixed["most_likely_path"]["champion"] == top
    assert len(fixed["most_likely_path"]["rounds"]) == 4


def test_most_likely_path_matches_top_champion():
    result = run_monte_carlo(2000, seed=42)
    champ_probs = result["team_stats"]["champion"]
    top_code = next(iter(champ_probs))
    path = result["most_likely_path"]
    assert path
    assert path["champion"] == top_code
    assert len(path["rounds"]) == 4
    assert path["rounds"][0]["id"] == "r32"
    assert len(path["rounds"][0]["winners"]) == 16
    assert path["final"]["champion"] == top_code


def test_most_likely_path_is_modal_full_knockout():
    from app.services.simulator import _knockout_path_key

    result = run_monte_carlo(500, seed=7)
    path = result["most_likely_path"]
    bracket = result["most_likely_bracket"]
    assert path["champion"] == bracket["champion"]
    key = _knockout_path_key(bracket)
    assert path["occurrences"] >= 1
    # Full path key must encode all knockout winners
    assert len(key.split("|")) == 6
