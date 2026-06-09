"""Official FIFA World Cup 2026 Round of 32 seeding."""

from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)

GROUP_LETTERS = list("ABCDEFGHIJKL")


class ThirdAdvancer(TypedDict):
    group: str
    code: str


def _fixed(position: str) -> dict:
    return {"kind": "fixed", "position": position}


def _third(eligible_groups: list[str], opponent_group: str) -> dict:
    return {
        "kind": "third",
        "eligible_groups": eligible_groups,
        "opponent_group": opponent_group,
    }


# Official R32 template — index 0 = bracket slot r32-1 (WC match 73).
R32_OFFICIAL_TEMPLATE: list[tuple[dict, dict]] = [
    (_fixed("2A"), _fixed("2B")),
    (_fixed("1E"), _third(["A", "B", "C", "D", "F"], "E")),
    (_fixed("1F"), _fixed("2C")),
    (_fixed("1C"), _fixed("2F")),
    (_fixed("1I"), _third(["C", "D", "F", "G", "H"], "I")),
    (_fixed("2E"), _fixed("2I")),
    (_fixed("1A"), _third(["C", "E", "F", "H", "I"], "A")),
    (_fixed("1L"), _third(["E", "H", "I", "J", "K"], "L")),
    (_fixed("1D"), _third(["B", "E", "F", "I", "J"], "D")),
    (_fixed("1G"), _third(["A", "E", "H", "I", "J"], "G")),
    (_fixed("2K"), _fixed("2L")),
    (_fixed("1H"), _fixed("2J")),
    (_fixed("1B"), _third(["E", "F", "G", "I", "J"], "B")),
    (_fixed("1J"), _fixed("2H")),
    (_fixed("1K"), _third(["D", "E", "I", "J", "L"], "K")),
    (_fixed("2D"), _fixed("2G")),
]


def third_advancers_with_groups(
    standings_by_group: dict[str, list[dict]],
    third_advancer_codes: list[str],
) -> list[ThirdAdvancer]:
    code_set = set(third_advancer_codes)
    out: list[ThirdAdvancer] = []
    for group, rows in standings_by_group.items():
        if len(rows) >= 3 and rows[2]["code"] in code_set:
            out.append({"group": group, "code": rows[2]["code"]})
    return sorted(out, key=lambda x: x["group"])


def qualifier_team_codes(
    standings_by_group: dict[str, list[dict]],
    third_advancers: list[str],
) -> set[str]:
    codes: set[str] = set()
    for rows in standings_by_group.values():
        if rows:
            codes.add(rows[0]["code"])
        if len(rows) > 1:
            codes.add(rows[1]["code"])
    codes.update(third_advancers)
    return codes


def _team_to_group_map(standings_by_group: dict[str, list[dict]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for group, rows in standings_by_group.items():
        for row in rows:
            mapping[row["code"]] = group
    return mapping


def _resolve_fixed_side(side: dict, standings_by_group: dict[str, list[dict]]) -> str | None:
    position = side["position"]
    group = position[1]
    rank = 0 if position[0] == "1" else 1
    rows = standings_by_group.get(group, [])
    if len(rows) <= rank:
        return None
    return rows[rank]["code"]


def assign_third_place_berths(
    advancing_thirds: list[ThirdAdvancer],
    slot_defs: list[dict],
) -> dict[int, str] | None:
    ordered = sorted(slot_defs, key=lambda s: len(s["eligible_groups"]))
    assignment: dict[int, str] = {}

    def backtrack(slot_idx: int, remaining: list[ThirdAdvancer]) -> bool:
        if slot_idx >= len(ordered):
            return True
        slot = ordered[slot_idx]
        eligible = slot["eligible_groups"]
        match_index = slot["match_index"]
        for i, team in enumerate(remaining):
            if team["group"] not in eligible:
                continue
            assignment[match_index] = team["code"]
            nxt = remaining[:i] + remaining[i + 1 :]
            if backtrack(slot_idx + 1, nxt):
                return True
        return False

    if not backtrack(0, advancing_thirds):
        return None
    return assignment


def build_r32_pairings(
    standings_by_group: dict[str, list[dict]],
    third_advancer_codes: list[str],
) -> list[tuple[str, str]]:
    advancing_thirds = third_advancers_with_groups(standings_by_group, third_advancer_codes)
    if len(advancing_thirds) != 8:
        logger.error("R32 seeding: expected 8 third-place advancers, got %s", len(advancing_thirds))
        return []

    third_slot_defs: list[dict] = []
    for match_index, (side_a, side_b) in enumerate(R32_OFFICIAL_TEMPLATE):
        for side in (side_a, side_b):
            if side["kind"] == "third":
                third_slot_defs.append(
                    {"match_index": match_index, "eligible_groups": side["eligible_groups"]}
                )

    third_by_match = assign_third_place_berths(advancing_thirds, third_slot_defs)
    if third_by_match is None:
        logger.error(
            "R32 seeding: could not assign third-place teams for groups %s",
            [t["group"] for t in advancing_thirds],
        )
        return []

    pairings: list[tuple[str, str]] = []
    for match_index, (side_a, side_b) in enumerate(R32_OFFICIAL_TEMPLATE):
        code_a = (
            _resolve_fixed_side(side_a, standings_by_group)
            if side_a["kind"] == "fixed"
            else third_by_match.get(match_index)
        )
        code_b = (
            _resolve_fixed_side(side_b, standings_by_group)
            if side_b["kind"] == "fixed"
            else third_by_match.get(match_index)
        )
        if not code_a or not code_b:
            logger.error("R32 seeding: missing team for match %s", match_index + 1)
            return []
        pairings.append((code_a, code_b))

    return pairings


def build_r32_slot_teams(pairings: list[tuple[str, str]]) -> dict[str, str]:
    slot_teams: dict[str, str] = {}
    for i, (home, away) in enumerate(pairings, start=1):
        slot = f"r32-{i}"
        slot_teams[f"{slot}:a"] = home
        slot_teams[f"{slot}:b"] = away
    return slot_teams


def validate_r32_slot_teams(
    slot_teams: dict[str, str],
    standings_by_group: dict[str, list[dict]],
    third_advancers: list[str],
) -> bool:
    codes = list(slot_teams.values())
    if len(codes) != 32:
        logger.error("R32 seeding: expected 32 slot entries, got %s", len(codes))
        return False

    unique = set(codes)
    if len(unique) != 32:
        logger.error("R32 seeding: duplicate teams in R32")
        return False

    expected = qualifier_team_codes(standings_by_group, third_advancers)
    if len(expected) != 32 or unique != expected:
        logger.error("R32 seeding: team set mismatch with qualifiers")
        return False

    team_group = _team_to_group_map(standings_by_group)
    for i in range(1, 17):
        a = slot_teams.get(f"r32-{i}:a")
        b = slot_teams.get(f"r32-{i}:b")
        if a and b and team_group.get(a) == team_group.get(b):
            logger.error("R32 seeding: same-group matchup in r32-%s", i)
            return False

    return True


def seed_r32_from_standings(
    standings_by_group: dict[str, list[dict]],
    third_advancers: list[str],
) -> dict[str, str]:
    pairings = build_r32_pairings(standings_by_group, third_advancers)
    if len(pairings) != 16:
        return {}
    slot_teams = build_r32_slot_teams(pairings)
    if not validate_r32_slot_teams(slot_teams, standings_by_group, third_advancers):
        return {}
    return slot_teams
