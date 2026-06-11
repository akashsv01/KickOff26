"""Tests for grounded chat context retrieval."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.chat_context import (
    _teams_mentioned,
    _wants_global_schedule,
    build_chat_context,
    build_schedule_snapshot,
)


def _match(
    home: str,
    away: str,
    *,
    kickoff: str,
    local_date: str,
    status: str = "scheduled",
    home_score: int | None = None,
    away_score: int | None = None,
    mid: int = 1,
) -> dict:
    return {
        "id": mid,
        "home_team": {"code": home, "name": home},
        "away_team": {"code": away, "name": away},
        "kickoff_at": kickoff,
        "local_date": local_date,
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "group_letter": "A",
        "venue": "Stadium",
        "city": "City",
    }


def test_wants_global_schedule_for_next_match_question():
    assert _wants_global_schedule("when is the next match")
    assert _wants_global_schedule("not my following teams, in general when is the next match")
    assert not _wants_global_schedule("when does my followed team play next")


def test_next_match_skips_finished_opening():
    now = datetime(2026, 6, 12, 1, 0, tzinfo=timezone.utc)
    matches = [
        _match(
            "MEX",
            "RSA",
            kickoff="2026-06-11T19:00:00+00:00",
            local_date="2026-06-11",
            status="finished",
            home_score=2,
            away_score=0,
            mid=1,
        ),
        _match(
            "KOR",
            "CZE",
            kickoff="2026-06-12T02:00:00+00:00",
            local_date="2026-06-11",
            status="scheduled",
            mid=2,
        ),
        _match(
            "BRA",
            "MAR",
            kickoff="2026-06-13T22:00:00+00:00",
            local_date="2026-06-13",
            status="scheduled",
            mid=3,
        ),
    ]
    snap = build_schedule_snapshot(matches, now)
    assert snap["next_match"] is not None
    assert snap["next_match"]["home_team"]["code"] == "KOR"
    assert snap["next_match"]["away_team"]["code"] == "CZE"


def test_live_match_is_next():
    now = datetime(2026, 6, 12, 2, 30, tzinfo=timezone.utc)
    matches = [
        _match(
            "MEX",
            "RSA",
            kickoff="2026-06-11T19:00:00+00:00",
            local_date="2026-06-11",
            status="finished",
            home_score=2,
            away_score=0,
        ),
        _match(
            "KOR",
            "CZE",
            kickoff="2026-06-12T02:00:00+00:00",
            local_date="2026-06-11",
            status="live",
            home_score=0,
            away_score=0,
        ),
    ]
    snap = build_schedule_snapshot(matches, now)
    assert snap["next_match"]["home_team"]["code"] == "KOR"
    assert len(snap["live"]) == 1


@pytest.mark.asyncio
async def test_context_includes_standings_for_group_question(setup_db):
    from app.db import async_session
    from app.models import Team

    async with async_session() as db:
        ctx = await build_chat_context(db, "Show me Group A standings", user=None)
        assert "Group A" in ctx or "group standings" in ctx.lower()
        assert "2026" in ctx


@pytest.mark.asyncio
async def test_teams_mentioned_by_name_and_code(setup_db):
    from app.db import async_session
    from app.models import Team
    from sqlalchemy import select

    async with async_session() as db:
        teams = list((await db.execute(select(Team).limit(48))).scalars().all())
        mex = next((t for t in teams if t.code == "MEX"), None)
        if not mex:
            pytest.skip("MEX not seeded")
        found = _teams_mentioned("When does Mexico play next?", teams)
        codes = [t.code for t in found]
        assert "MEX" in codes


@pytest.mark.asyncio
async def test_global_next_match_context_mentions_snapshot(setup_db):
    from app.db import async_session

    async with async_session() as db:
        ctx = await build_chat_context(
            db, "When is the next match of the world cup in general?", user=None
        )
        assert "NEXT TOURNAMENT MATCH" in ctx
        assert "tournament-wide" in ctx.lower() or "followed-team" in ctx.lower()


@pytest.mark.asyncio
async def test_guest_context_notes_login(setup_db):
    from app.db import async_session

    async with async_session() as db:
        ctx = await build_chat_context(db, "What did I predict for the final?", user=None)
        assert "guest" in ctx.lower() or "login" in ctx.lower()
