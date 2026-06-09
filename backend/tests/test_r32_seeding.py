"""Tests for official Round of 32 seeding from saved group qualifiers."""

from __future__ import annotations

from app.services.bracket_standings import rank_third_placed
from app.services.r32_seeding import (
    build_r32_pairings,
    build_r32_slot_teams,
    qualifier_team_codes,
    seed_r32_from_standings,
    validate_r32_slot_teams,
)


def _row(code: str, points: int, gd: int = 0, gf: int = 0) -> dict:
    return {
        "code": code,
        "name": code,
        "played": 3,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "gf": gf,
        "ga": gf - gd,
        "gd": gd,
        "points": points,
        "rank": 0,
    }


def _full_tournament_standings() -> dict[str, list[dict]]:
    """Synthetic 12-group standings with distinct team codes per finisher."""
    standings: dict[str, list[dict]] = {}
    for i, group in enumerate("ABCDEFGHIJKL"):
        third_pts = 6 - (i % 5)  # spread third-place points for ranking
        standings[group] = [
            _row(f"W{group}", 9, gd=3, gf=5),
            _row(f"R{group}", 6, gd=1, gf=4),
            _row(f"T{group}", third_pts, gd=0, gf=2 + (i % 2)),
            _row(f"L{group}", 0, gd=-4, gf=1),
        ]
    return standings


def test_r32_seeding_thirty_two_unique_qualifiers():
    standings = _full_tournament_standings()
    third_advancers = rank_third_placed(standings)
    assert len(third_advancers) == 8

    slot_teams = seed_r32_from_standings(standings, third_advancers)
    assert len(slot_teams) == 32

    codes = list(slot_teams.values())
    assert len(set(codes)) == 32

    expected = qualifier_team_codes(standings, third_advancers)
    assert set(codes) == expected
    assert validate_r32_slot_teams(slot_teams, standings, third_advancers)


def test_r32_no_duplicate_teams_in_pairings():
    standings = _full_tournament_standings()
    third_advancers = rank_third_placed(standings)
    pairings = build_r32_pairings(standings, third_advancers)

    assert len(pairings) == 16
    all_codes = [code for pair in pairings for code in pair]
    assert len(all_codes) == 32
    assert len(set(all_codes)) == 32


def test_r32_no_same_group_matchups():
    standings = _full_tournament_standings()
    third_advancers = rank_third_placed(standings)
    slot_teams = build_r32_slot_teams(build_r32_pairings(standings, third_advancers))

    team_group = {row["code"]: g for g, rows in standings.items() for row in rows}
    for i in range(1, 17):
        a = slot_teams[f"r32-{i}:a"]
        b = slot_teams[f"r32-{i}:b"]
        assert team_group[a] != team_group[b]


def test_r32_official_template_first_match_is_runners_up_a_vs_b():
    standings = _full_tournament_standings()
    third_advancers = rank_third_placed(standings)
    pairings = build_r32_pairings(standings, third_advancers)

    assert pairings[0] == ("RA", "RB")
