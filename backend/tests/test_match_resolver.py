import pytest

from app.services.match_resolver import resolve_match_probs, sample_match_result, get_winner_code


def test_probs_sum_to_one():
    probs = resolve_match_probs("BRA", "ARG", neutral=True)
    assert abs(sum(probs.values()) - 1.0) < 0.01


def test_sample_produces_valid_outcome():
    import numpy as np

    rng = np.random.default_rng(42)
    outcomes = {sample_match_result("FRA", "GER", rng=rng) for _ in range(50)}
    assert outcomes <= {"home", "draw", "away"}


def test_get_winner_code():
    assert get_winner_code("BRA", "ARG", "home") == "BRA"
    assert get_winner_code("BRA", "ARG", "away") == "ARG"
    assert get_winner_code("BRA", "ARG", "draw") is None


def test_weaker_team_lower_win_prob():
    probs = resolve_match_probs("BRA", "SLV", neutral=True)
    assert probs["home"] > probs["away"]
