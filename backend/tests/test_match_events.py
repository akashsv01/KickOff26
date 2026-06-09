"""Tests for durable match_events timeline storage."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db import async_session
from app.models import Match, MatchEvent, MatchStatus
from app.services.matchday_alerts import UNKNOWN_PLAYER, parse_api_events
from app.services.match_events import fetch_events_for_match, insert_new_events
from app.services.matchday import get_match_detail


@pytest.mark.asyncio
async def test_duplicate_poll_inserts_once(setup_db):
    async with async_session() as db:
        match = (
            await db.execute(select(Match).where(Match.status == MatchStatus.LIVE).limit(1))
        ).scalar_one_or_none()
        assert match is not None

        event = {"type": "goal", "minute": 61, "team": "away", "player": "Promes"}
        first = await insert_new_events(db, match.id, [event])
        second = await insert_new_events(db, match.id, [event])
        await db.commit()

        assert len(first) == 1
        assert len(second) == 0

        count = (
            await db.execute(
                select(func.count()).select_from(MatchEvent).where(MatchEvent.match_id == match.id)
            )
        ).scalar_one()
        stored = await fetch_events_for_match(db, match.id)
        assert count == len(stored)
        assert count >= 1
        assert stored[-1]["player"] == "Promes"


@pytest.mark.asyncio
async def test_events_persist_across_sessions(setup_db):
    match_id: int
    expected_count: int

    async with async_session() as db:
        match = (
            await db.execute(select(Match).where(Match.status == MatchStatus.LIVE).limit(1))
        ).scalar_one_or_none()
        assert match is not None
        match_id = match.id
        await insert_new_events(
            db,
            match_id,
            [{"type": "yellow_card", "minute": 70, "team": "home", "player": "Lozano"}],
        )
        await db.commit()
        expected_count = len(await fetch_events_for_match(db, match_id))

    async with async_session() as db:
        after_restart = await fetch_events_for_match(db, match_id)
        assert len(after_restart) == expected_count
        detail = await get_match_detail(db, match_id)
        assert detail is not None
        assert detail["events"] == after_restart


@pytest.mark.asyncio
async def test_match_detail_timeline_equals_stored_rows(setup_db):
    async with async_session() as db:
        match = (
            await db.execute(select(Match).where(Match.status == MatchStatus.LIVE).limit(1))
        ).scalar_one_or_none()
        assert match is not None
        stored = await fetch_events_for_match(db, match.id)
        detail = await get_match_detail(db, match.id)
        assert detail is not None
        assert detail["events"] == stored


def test_api_missing_player_becomes_unknown():
    raw = [
        {
            "time": {"elapsed": 10},
            "team": {"id": 1},
            "type": "Goal",
            "detail": "Normal Goal",
        }
    ]
    parsed = parse_api_events(raw, api_home_id=1)
    assert len(parsed) == 1
    assert parsed[0]["player"] == UNKNOWN_PLAYER


def test_api_uses_real_player_name():
    raw = [
        {
            "time": {"elapsed": 61},
            "team": {"id": 2},
            "player": {"name": "Bukayo Saka"},
            "type": "Goal",
            "detail": "Normal Goal",
        }
    ]
    parsed = parse_api_events(raw, api_home_id=1)
    assert parsed[0]["player"] == "Bukayo Saka"
    assert parsed[0]["player"] != "Midfielder"
