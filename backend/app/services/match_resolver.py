"""Resolve a match between two teams using the shared win-probability engine."""

from __future__ import annotations

import numpy as np

from app.models.win_probability import engine


def resolve_match_probs(
    home_code: str,
    away_code: str,
    neutral: bool = True,
) -> dict[str, float]:
    """Return win/draw/loss probabilities for a matchup."""
    return engine.pre_match_probabilities(home_code, away_code, neutral=neutral)


def sample_match_result(
    home_code: str,
    away_code: str,
    rng: np.random.Generator | None = None,
    neutral: bool = True,
) -> str:
    """
    Sample a match outcome: 'home', 'draw', or 'away'.
    Used by Monte Carlo simulator - never duplicate probability logic elsewhere.
    """
    probs = resolve_match_probs(home_code, away_code, neutral=neutral)
    rng = rng or np.random.default_rng()
    outcomes = ["home", "draw", "away"]
    weights = [probs["home"], probs["draw"], probs["away"]]
    return rng.choice(outcomes, p=weights)


def get_winner_code(
    home_code: str,
    away_code: str,
    outcome: str,
) -> str | None:
    """Return winning team code, or None for draw."""
    if outcome == "home":
        return home_code
    if outcome == "away":
        return away_code
    return None
