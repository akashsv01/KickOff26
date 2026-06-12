"""Tests for bundled roster seed (team_rosters_2026.json)."""

import pytest
from sqlalchemy import func, select

from app.db import async_session
from app.models import Team, TeamRoster
from app.services.roster_seed import (
    ROSTER_BUNDLE_PATH,
    find_roster_bundle_entry,
    load_roster_bundle,
    seed_team_rosters_from_bundle,
    _slug_index,
)
from app.services.team_name_resolve import zafronix_slug_for_team
from app.services.tournament_2026 import OFFICIAL_TEAMS


class _Team:
    def __init__(self, code: str, name: str):
        self.code = code
        self.name = name


def test_roster_bundle_covers_all_48_official_teams():
    entries = load_roster_bundle(ROSTER_BUNDLE_PATH)
    index = _slug_index(entries)
    missing = []
    for t in OFFICIAL_TEAMS:
        team = _Team(t["code"], t["name"])
        entry = find_roster_bundle_entry(team, index)
        if not entry or not entry.get("players"):
            missing.append(t["code"])
    assert missing == [], f"Bundle missing squads for: {missing}"


def test_cod_matches_democratic_republic_of_congo():
    entries = load_roster_bundle(ROSTER_BUNDLE_PATH)
    index = _slug_index(entries)
    team = _Team("COD", "DR Congo")
    entry = find_roster_bundle_entry(team, index)
    assert entry is not None
    assert entry.get("zafronix_slug") == "Democratic Republic of the Congo"
    assert len(entry.get("players") or []) > 0


@pytest.mark.asyncio
async def test_seed_team_rosters_from_bundle(setup_db):
    async with async_session() as db:
        result = await seed_team_rosters_from_bundle(db)
        await db.commit()

    assert result["teams"] == 48
    assert result["ready"] == 48
    assert result["missing"] == []

    async with async_session() as db:
        ready_count = (
            await db.execute(
                select(func.count())
                .select_from(TeamRoster)
                .where(TeamRoster.fetch_status == "ready")
            )
        ).scalar_one()
        teams_with_players = (
            await db.execute(
                select(func.count())
                .select_from(TeamRoster)
                .join(Team, TeamRoster.team_id == Team.id)
                .where(Team.code.in_([t["code"] for t in OFFICIAL_TEAMS]))
                .where(TeamRoster.fetch_status == "ready")
            )
        ).scalar_one()

    assert ready_count >= 48
    assert teams_with_players == 48
