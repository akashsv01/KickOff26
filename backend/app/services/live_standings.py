"""Live group standings derived from current DB match state.

Driven by the live poller (real scores) so standings move in real time - a match in
progress contributes its current (even 0-0) result and its group is flagged "live".
Tiebreakers: points, goal difference, goals scored. Highlights top-2 per group plus
the best 8 third-placed teams (the 2026 round-of-32 qualification rule).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Match, MatchStatus, Team
from app.services.bracket_standings import _empty_row, _standing_sort_key, apply_match_result
from app.services.openfootball import OFFICIAL_EXTERNAL_PREFIX


def _counts(match: Match) -> bool:
    """A match contributes to standings once it is live or finished."""
    return match.status in (MatchStatus.LIVE, MatchStatus.FINISHED)


async def compute_live_standings(db: AsyncSession) -> dict:
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(
            Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"),
            Match.stage == "group",
        )
        .order_by(Match.group_letter, Match.kickoff_at)
    )
    matches = result.scalars().all()

    groups: dict[str, dict[str, dict]] = {}
    group_live: dict[str, bool] = {}

    for m in matches:
        grp = m.group_letter or (m.home_team.group_letter if m.home_team else None)
        if not grp:
            continue
        rows = groups.setdefault(grp, {})
        for team in (m.home_team, m.away_team):
            if team and team.code not in rows:
                rows[team.code] = _empty_row(team.code, team.name)
        if m.status == MatchStatus.LIVE:
            group_live[grp] = True
        if _counts(m) and m.home_team and m.away_team:
            hs = m.home_score or 0
            aws = m.away_score or 0
            apply_match_result(rows[m.home_team.code], rows[m.away_team.code], hs, aws)

    # Rank each group.
    standings: dict[str, list[dict]] = {}
    for grp, rows in groups.items():
        ordered = sorted(rows.values(), key=_standing_sort_key, reverse=True)
        for i, row in enumerate(ordered, start=1):
            row["rank"] = i
            row["gd"] = row["gf"] - row["ga"]
        standings[grp] = ordered

    # Best 8 third-placed teams.
    thirds = [rows[2] for rows in standings.values() if len(rows) >= 3]
    thirds_sorted = sorted(thirds, key=_standing_sort_key, reverse=True)
    third_codes = {r["code"] for r in thirds_sorted[:8]}

    out_groups = []
    for grp in sorted(standings.keys()):
        rows = standings[grp]
        enriched_rows = []
        for row in rows:
            if row["rank"] <= 2:
                qualification = "auto"
            elif row["rank"] == 3 and row["code"] in third_codes:
                qualification = "third"
            else:
                qualification = None
            enriched_rows.append({**row, "qualification": qualification})
        out_groups.append(
            {"group": grp, "live": bool(group_live.get(grp)), "rows": enriched_rows}
        )

    return {
        "groups": out_groups,
        "best_thirds": [r["code"] for r in thirds_sorted[:8]],
        "any_live": any(group_live.values()),
    }
