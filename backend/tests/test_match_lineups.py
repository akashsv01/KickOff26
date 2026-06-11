"""Tests for durable match lineups (fetch-once, store, detail rendering)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db import async_session
from app.models import Match, MatchLineup, MatchStatus
from app.services.match_lineups import (
    LINEUP_FETCH_BEFORE,
    LINEUP_RETRY_DELAY,
    fetch_and_store_lineup,
    in_lineup_fetch_window,
    lineup_to_detail_fields,
    matches_needing_lineup_fetch,
    parse_fixture_lineups,
    store_lineup,
)
from app.services.matchday import get_match_detail


def _sample_bundle() -> dict:
    return {
        "teams": {"home": {"id": 10}, "away": {"id": 20}},
        "lineups": [
            {
                "team": {"id": 10},
                "formation": "4-3-3",
                "coach": {"name": "Coach Home"},
                "startXI": [
                    {"player": {"id": 1, "name": "Keeper", "number": 1, "pos": "G", "grid": "1:1"}},
                    {"player": {"id": 2, "name": "Defender", "number": 2, "pos": "D", "grid": "2:1"}},
                ],
                "substitutes": [
                    {"player": {"id": 3, "name": "Sub One", "number": 12, "pos": "M", "grid": None}},
                ],
            },
            {
                "team": {"id": 20},
                "formation": "4-4-2",
                "coach": {"name": "Coach Away"},
                "startXI": [
                    {"player": {"id": 4, "name": "Away GK", "number": 1, "pos": "G", "grid": "1:1"}},
                    {"player": {"id": 5, "name": "Away ST", "number": 9, "pos": "F", "grid": "4:2"}},
                ],
                "substitutes": [],
            },
        ],
        "events": [
            {
                "time": {"elapsed": 10},
                "team": {"id": 10},
                "player": {"name": "Keeper"},
                "type": "Goal",
                "detail": "Normal Goal",
            }
        ],
    }


def test_parse_fixture_lineups_maps_home_away():
    home, away = parse_fixture_lineups(_sample_bundle())
    assert home["formation"] == "4-3-3"
    assert away["formation"] == "4-4-2"
    assert home["starting_xi"][0]["name"] == "Keeper"
    assert home["starting_xi"][0]["grid"] == "1:1"
    assert home["bench"][0]["name"] == "Sub One"
    assert away["coach"] == "Coach Away"


def test_lineup_to_detail_fields_empty_when_not_ready():
    fields = lineup_to_detail_fields(None)
    assert fields["home_lineup"] == []
    assert fields["lineups"] is None

    row = MatchLineup(match_id=1, fetch_status="unavailable")
    fields = lineup_to_detail_fields(row)
    assert fields["home_lineup"] == []

    demo_row = MatchLineup(
        match_id=2,
        fetch_status="ready",
        source="demo",
        home_xi=[{"number": 1, "name": "Demo", "position": "GK"}],
        away_xi=[{"number": 2, "name": "Demo", "position": "GK"}],
    )
    assert lineup_to_detail_fields(demo_row)["home_lineup"] == []


def test_in_lineup_fetch_window():
    now = datetime(2026, 6, 11, 18, 55, tzinfo=timezone.utc)
    kickoff = now + timedelta(minutes=5)
    match = Match(kickoff_at=kickoff, status=MatchStatus.SCHEDULED)
    assert in_lineup_fetch_window(match, now)

    too_early = kickoff - LINEUP_FETCH_BEFORE - timedelta(minutes=1)
    assert not in_lineup_fetch_window(match, too_early)


@pytest.mark.asyncio
async def test_store_and_detail_render(setup_db):
    async with async_session() as db:
        match = (
            await db.execute(select(Match).where(Match.status == MatchStatus.LIVE).limit(1))
        ).scalar_one_or_none()
        assert match is not None

        home, away = parse_fixture_lineups(_sample_bundle())
        await store_lineup(db, match.id, home, away, source="api")

        detail = await get_match_detail(db, match.id)
        assert detail is not None
        assert detail["home_lineup"][0]["name"] == "Keeper"
        assert detail["lineups"]["home"]["formation"] == "4-3-3"
        assert detail["lineups"]["away"]["bench"] == []
        await db.rollback()


@pytest.mark.asyncio
async def test_demo_lineups_not_exposed_in_detail(setup_db):
    async with async_session() as db:
        match = (
            await db.execute(select(Match).where(Match.status == MatchStatus.LIVE).limit(1))
        ).scalar_one_or_none()
        assert match is not None

        home, away = parse_fixture_lineups(_sample_bundle())
        await store_lineup(db, match.id, home, away, source="demo")

        detail = await get_match_detail(db, match.id)
        assert detail is not None
        assert detail["home_lineup"] == []
        assert detail["lineups"] is None


@pytest.mark.asyncio
async def test_empty_lineup_schedules_single_retry(setup_db, monkeypatch):
    async with async_session() as db:
        match = (
            await db.execute(
                select(Match)
                .where(Match.status == MatchStatus.SCHEDULED, Match.api_fixture_id.is_(None))
                .limit(1)
            )
        ).scalar_one_or_none()
        assert match is not None
        existing = (
            await db.execute(select(MatchLineup).where(MatchLineup.match_id == match.id))
        ).scalar_one_or_none()
        if existing:
            await db.delete(existing)
        match.api_fixture_id = 999001
        kickoff = datetime.now(timezone.utc) + timedelta(minutes=8)
        match.kickoff_at = kickoff
        await db.flush()

        class FakeClient:
            async def fetch_fixture_by_id(self, fixture_id: int):
                return {"teams": {"home": {"id": 1}, "away": {"id": 2}}, "lineups": []}

            async def is_halted(self):
                return False

        ok = await fetch_and_store_lineup(db, match, FakeClient())
        assert ok is False
        row = (
            await db.execute(select(MatchLineup).where(MatchLineup.match_id == match.id))
        ).scalar_one()
        assert row.fetch_status == "retry"
        assert row.fetch_attempts == 1
        assert row.retry_after is not None

        row.retry_after = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.flush()
        pending = await matches_needing_lineup_fetch(db)
        assert match.id in [m.id for m in pending]

        ok2 = await fetch_and_store_lineup(db, match, FakeClient())
        assert ok2 is False
        row = (
            await db.execute(select(MatchLineup).where(MatchLineup.match_id == match.id))
        ).scalar_one()
        assert row.fetch_status == "unavailable"
        assert row.fetch_attempts == 2

        pending_after = await matches_needing_lineup_fetch(db)
        assert match.id not in [m.id for m in pending_after]
        await db.rollback()


@pytest.mark.asyncio
async def test_matches_needing_fetch_respects_retry_delay(setup_db):
    async with async_session() as db:
        match = (
            await db.execute(select(Match).where(Match.status == MatchStatus.SCHEDULED).limit(1))
        ).scalar_one_or_none()
        assert match is not None
        match.api_fixture_id = 888
        match.kickoff_at = datetime.now(timezone.utc) + timedelta(minutes=9)
        row = (
            await db.execute(select(MatchLineup).where(MatchLineup.match_id == match.id))
        ).scalar_one_or_none()
        if row is None:
            row = MatchLineup(match_id=match.id)
            db.add(row)
        row.fetch_status = "retry"
        row.fetch_attempts = 1
        row.home_xi = []
        row.away_xi = []
        row.retry_after = datetime.now(timezone.utc) + LINEUP_RETRY_DELAY
        await db.flush()
        pending = await matches_needing_lineup_fetch(db)
        assert match.id not in [m.id for m in pending]
        await db.rollback()
