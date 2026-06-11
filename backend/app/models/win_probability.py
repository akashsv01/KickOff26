"""Poisson/Elo win-probability engine with live in-match updates."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.tournament_2026 import HISTORICAL_RESULTS, OFFICIAL_TEAMS as MOCK_TEAMS

HOME_ADVANTAGE_ELO = 65
BASE_GOALS = 1.32
ELO_GOAL_SCALE = 0.52  # how strongly Elo gap affects expected goals
ELO_K = 16  # light calibration - preserve seed spreads


@dataclass
class TeamRatings:
    code: str
    elo: float
    attack: float = 1.0
    defense: float = 1.0


def _expected_score(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400))


def _poisson_prob(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def _match_outcome_probs(lambda_home: float, lambda_away: float, max_goals: int = 10) -> tuple[float, float, float]:
    """Return (P_home_win, P_draw, P_away_win) from Poisson goal distributions."""
    p_home, p_draw, p_away = 0.0, 0.0, 0.0
    for hg in range(max_goals + 1):
        ph = _poisson_prob(hg, lambda_home)
        for ag in range(max_goals + 1):
            pa = _poisson_prob(ag, lambda_away)
            p = ph * pa
            if hg > ag:
                p_home += p
            elif hg == ag:
                p_draw += p
            else:
                p_away += p
    total = p_home + p_draw + p_away
    if total > 0:
        return p_home / total, p_draw / total, p_away / total
    return 1 / 3, 1 / 3, 1 / 3


def _live_outcome_probs(
    home_score: int,
    away_score: int,
    lambda_home_rem: float,
    lambda_away_rem: float,
    max_add: int = 8,
) -> tuple[float, float, float]:
    """Probability of final outcome given current score and Poisson rates for remaining time."""
    p_home, p_draw, p_away = 0.0, 0.0, 0.0
    for add_h in range(max_add + 1):
        ph = _poisson_prob(add_h, lambda_home_rem)
        for add_a in range(max_add + 1):
            pa = _poisson_prob(add_a, lambda_away_rem)
            p = ph * pa
            fh, fa = home_score + add_h, away_score + add_a
            if fh > fa:
                p_home += p
            elif fh == fa:
                p_draw += p
            else:
                p_away += p
    total = p_home + p_draw + p_away
    if total > 0:
        return p_home / total, p_draw / total, p_away / total
    return 1 / 3, 1 / 3, 1 / 3


class WinProbabilityEngine:
    """Pre-match Poisson/Elo model with live in-match probability updates."""

    def __init__(self) -> None:
        self._ratings: dict[str, TeamRatings] = {}
        self._build_ratings_from_history()

    def _build_ratings_from_history(self) -> None:
        """Seed Elo from team data, lightly calibrate with historical results."""
        for t in MOCK_TEAMS:
            self._ratings[t["code"]] = TeamRatings(code=t["code"], elo=float(t["elo"]))

        for home, away, hs, aws in HISTORICAL_RESULTS:
            if home in self._ratings and away in self._ratings:
                self._update_elo(home, away, hs, aws)

        avg_elo = sum(r.elo for r in self._ratings.values()) / max(len(self._ratings), 1)
        for r in self._ratings.values():
            diff = (r.elo - avg_elo) / 400
            r.attack = math.exp(diff * 0.45)
            r.defense = math.exp(-diff * 0.45)

    def _update_elo(self, home: str, away: str, hs: int, aws: int) -> None:
        rh = self._ratings[home]
        ra = self._ratings[away]
        exp_h = _expected_score(rh.elo + HOME_ADVANTAGE_ELO, ra.elo)
        if hs > aws:
            score_h, score_a = 1.0, 0.0
        elif hs < aws:
            score_h, score_a = 0.0, 1.0
        else:
            score_h, score_a = 0.5, 0.5
        rh.elo += ELO_K * (score_h - exp_h)
        ra.elo += ELO_K * (score_a - (1 - exp_h))

    def get_elo(self, team_code: str) -> float:
        return self._ratings.get(team_code, TeamRatings(team_code, 1500)).elo

    def _goal_lambdas(self, home_code: str, away_code: str, neutral: bool, time_frac: float = 1.0) -> tuple[float, float]:
        rh = self._ratings.get(home_code, TeamRatings(home_code, 1500))
        ra = self._ratings.get(away_code, TeamRatings(away_code, 1500))
        home_elo = rh.elo + (0 if neutral else HOME_ADVANTAGE_ELO)
        elo_diff = home_elo - ra.elo
        lam_h = BASE_GOALS * math.exp(elo_diff * ELO_GOAL_SCALE / 400) * time_frac
        lam_a = BASE_GOALS * math.exp(-elo_diff * ELO_GOAL_SCALE / 400) * time_frac
        return (
            min(max(lam_h, 0.35), 2.75),
            min(max(lam_a, 0.35), 2.75),
        )

    def pre_match_probabilities(
        self,
        home_code: str,
        away_code: str,
        neutral: bool = False,
    ) -> dict[str, float]:
        """Poisson/Elo pre-match win/draw/loss probabilities."""
        lam_h, lam_a = self._goal_lambdas(home_code, away_code, neutral)
        p_h, p_d, p_a = _match_outcome_probs(lam_h, lam_a)

        # Slight draw adjustment for very close matchups only
        rh = self._ratings.get(home_code, TeamRatings(home_code, 1500))
        ra = self._ratings.get(away_code, TeamRatings(away_code, 1500))
        elo_gap = abs(rh.elo - ra.elo)
        if elo_gap < 80:
            draw_boost = 0.04 * (1 - elo_gap / 80)
            p_d = min(p_d + draw_boost, 0.38)
            total = p_h + p_d + p_a
            return {"home": p_h / total, "draw": p_d / total, "away": p_a / total}

        return {"home": p_h, "draw": p_d, "away": p_a}

    def live_probabilities(
        self,
        home_code: str,
        away_code: str,
        home_score: int,
        away_score: int,
        minute: int,
        events: list[dict] | None = None,
        neutral: bool = False,
    ) -> dict[str, float]:
        """Update probabilities from score, clock, and events via conditional Poisson."""
        events = events or []
        remaining_frac = max(0.04, (90 - min(max(minute, 0), 90)) / 90) ** 0.85

        home_reds = sum(1 for e in events if e.get("type") == "red_card" and e.get("team") == "home")
        away_reds = sum(1 for e in events if e.get("type") == "red_card" and e.get("team") == "away")
        home_mod = 0.82 ** home_reds
        away_mod = 0.82 ** away_reds

        lam_h, lam_a = self._goal_lambdas(home_code, away_code, neutral, time_frac=remaining_frac)
        lam_h *= home_mod
        lam_a *= away_mod

        p_h, p_d, p_a = _live_outcome_probs(home_score, away_score, lam_h, lam_a)

        # Late-game score-state nudge
        score_diff = home_score - away_score
        if minute >= 80:
            if score_diff > 0:
                boost = min(0.25, score_diff * 0.08 + (minute - 80) * 0.02)
                p_h = min(0.97, p_h + boost)
                p_a = max(0.01, p_a - boost * 0.7)
            elif score_diff < 0:
                boost = min(0.25, abs(score_diff) * 0.08 + (minute - 80) * 0.02)
                p_a = min(0.97, p_a + boost)
                p_h = max(0.01, p_h - boost * 0.7)

        total = p_h + p_d + p_a
        return {"home": p_h / total, "draw": p_d / total, "away": p_a / total}


engine = WinProbabilityEngine()
