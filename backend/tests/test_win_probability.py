import pytest

from app.models.win_probability import WinProbabilityEngine


@pytest.fixture
def engine():
    return WinProbabilityEngine()


def test_pre_match_probs_sum_to_one(engine):
    probs = engine.pre_match_probabilities("BRA", "ARG", neutral=True)
    assert abs(probs["home"] + probs["draw"] + probs["away"] - 1.0) < 0.01


def test_strong_vs_weak_lopsided(engine):
    """Top side vs weak side should produce realistic lopsided split, not ~33/33/33."""
    probs = engine.pre_match_probabilities("BRA", "UZB", neutral=True)
    assert probs["home"] > 0.55
    assert probs["away"] < 0.20


def test_different_opponents_differ(engine):
    vs_weak = engine.pre_match_probabilities("BRA", "UZB", neutral=True)
    vs_strong = engine.pre_match_probabilities("BRA", "ARG", neutral=True)
    assert abs(vs_weak["home"] - vs_strong["home"]) > 0.15


def test_stronger_team_favored(engine):
    probs = engine.pre_match_probabilities("BRA", "UZB", neutral=True)
    assert probs["home"] > probs["away"]


def test_home_advantage(engine):
    neutral = engine.pre_match_probabilities("USA", "MEX", neutral=True)
    home = engine.pre_match_probabilities("USA", "MEX", neutral=False)
    assert home["home"] >= neutral["home"]


def test_live_probs_with_lead(engine):
    pre = engine.pre_match_probabilities("FRA", "GER", neutral=True)
    live = engine.live_probabilities("FRA", "GER", 2, 0, 75, [], neutral=True)
    assert live["home"] > pre["home"]


def test_live_shifts_from_pre_match_baseline(engine):
    pre = engine.pre_match_probabilities("BRA", "UZB", neutral=True)
    live = engine.live_probabilities(
        "BRA", "UZB", 2, 1, 58, [{"type": "goal", "minute": 34, "team": "home"}], neutral=True
    )
    assert live["home"] > pre["home"]


def test_red_card_shifts_probs(engine):
    no_card = engine.live_probabilities("ENG", "ESP", 0, 0, 30, [], neutral=True)
    with_red = engine.live_probabilities(
        "ENG", "ESP", 0, 0, 30, [{"type": "red_card", "team": "home"}], neutral=True
    )
    assert with_red["away"] > no_card["away"]


def test_elo_ratings_exist(engine):
    assert engine.get_elo("BRA") > engine.get_elo("UZB")
