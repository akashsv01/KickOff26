"""Group-stage standings and knockout seeding from user-entered results."""

from __future__ import annotations

from typing import TypedDict

from app.services.r32_seeding import (
    build_r32_pairings,
    build_r32_slot_teams,
    seed_r32_from_standings,
    validate_r32_slot_teams,
)


class StandingRow(TypedDict):
    code: str
    name: str
    played: int
    won: int
    drawn: int
    lost: int
    gf: int
    ga: int
    gd: int
    points: int
    rank: int


def _empty_row(code: str, name: str) -> dict:
    return {
        "code": code,
        "name": name,
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "gf": 0,
        "ga": 0,
        "gd": 0,
        "points": 0,
        "rank": 0,
    }


def _standing_sort_key(row: dict) -> tuple:
    """Descending: points, GD, GF; then ascending name for a stable order."""
    gf = int(row.get("gf") or 0)
    ga = int(row.get("ga") or 0)
    if "ga" in row:
        gd = gf - ga
    else:
        gd = int(row.get("gd") if row.get("gd") is not None else gf - ga)
    name = (row.get("name") or row.get("code") or "").casefold()
    return (-int(row.get("points") or 0), -gd, -gf, name)


def apply_match_result(home: dict, away: dict, hs: int, aws: int) -> None:
    home["played"] += 1
    away["played"] += 1
    home["gf"] += hs
    home["ga"] += aws
    away["gf"] += aws
    away["ga"] += hs
    if hs > aws:
        home["won"] += 1
        home["points"] += 3
        away["lost"] += 1
    elif hs < aws:
        away["won"] += 1
        away["points"] += 3
        home["lost"] += 1
    else:
        home["drawn"] += 1
        away["drawn"] += 1
        home["points"] += 1
        away["points"] += 1
    home["gd"] = home["gf"] - home["ga"]
    away["gd"] = away["gf"] - away["ga"]


def compute_group_standings(
    teams: list[dict],
    fixtures: list[dict],
    results: dict[str | int, dict],
) -> list[StandingRow]:
    """Build standings from fixture results keyed by match id (str or int)."""
    rows = {t["code"]: _empty_row(t["code"], t["name"]) for t in teams}

    for fixture in fixtures:
        fid = fixture["id"]
        result = results.get(fid) or results.get(str(fid))
        if not result:
            continue
        hs = int(result.get("home_score", 0))
        aws = int(result.get("away_score", 0))
        home_code = fixture["home"]["code"]
        away_code = fixture["away"]["code"]
        if home_code not in rows or away_code not in rows:
            continue
        apply_match_result(rows[home_code], rows[away_code], hs, aws)

    sorted_rows = sorted(rows.values(), key=_standing_sort_key)
    for i, row in enumerate(sorted_rows, start=1):
        row["rank"] = i
        row["gd"] = row["gf"] - row["ga"]
    return sorted_rows  # type: ignore[return-value]


def compute_all_standings(
    groups: dict[str, list[dict]],
    fixtures_by_group: dict[str, list[dict]],
    results: dict[str | int, dict],
) -> dict[str, list[StandingRow]]:
    out: dict[str, list[StandingRow]] = {}
    for group, teams in groups.items():
        out[group] = compute_group_standings(teams, fixtures_by_group.get(group, []), results)
    return out


def rank_third_placed(standings_by_group: dict[str, list[StandingRow]]) -> list[str]:
    """Top 8 third-placed teams: points, goal difference, goals scored."""
    thirds: list[StandingRow] = []
    for rows in standings_by_group.values():
        if len(rows) >= 3:
            thirds.append(rows[2])
    thirds.sort(key=_standing_sort_key)
    return [r["code"] for r in thirds[:8]]


def qualifier_team_ids(
    standings_by_group: dict[str, list[StandingRow]],
    third_advancers: list[str],
    teams_by_code: dict[str, dict],
) -> list[int]:
    """Team IDs for auto-qualified sides (top 2 per group + best 8 thirds)."""
    codes: set[str] = set(third_advancers)
    for rows in standings_by_group.values():
        if len(rows) >= 2:
            codes.add(rows[0]["code"])
            codes.add(rows[1]["code"])
    ids: list[int] = []
    for code in sorted(codes):
        team = teams_by_code.get(code)
        if team and team.get("id"):
            ids.append(int(team["id"]))
    return ids
