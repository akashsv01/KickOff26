"""Tests for World Cup poller scope, rate guard, and batch-only refresh."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Match, MatchStatus
from app.services import worldcup_rate_limit as rate_mod
from app.services.worldcup_poll_scope import match_in_kickoff_window, should_apply_game
from app.services.worldcup_poller import _apply_games_batch, poll_once
from app.services.worldcup_parse import derive_status


def _match(**kwargs) -> Match:
    defaults = dict(
        id=1,
        home_team_id=1,
        away_team_id=2,
        status=MatchStatus.SCHEDULED,
        kickoff_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        api_object_id="abc123",
    )
    defaults.update(kwargs)
    return Match(**defaults)


def test_should_apply_live_match():
    game = {"finished": "FALSE", "time_elapsed": "live", "home_score": "1", "away_score": "0"}
    match = _match(status=MatchStatus.LIVE)
    assert should_apply_game(game, match) is True


def test_should_apply_kickoff_transition():
    game = {"finished": "FALSE", "time_elapsed": "live", "home_score": "0", "away_score": "0"}
    match = _match(status=MatchStatus.SCHEDULED)
    assert should_apply_game(game, match) is True
    assert derive_status(game) == MatchStatus.LIVE


def test_should_skip_far_future_scheduled():
    game = {"finished": "FALSE", "time_elapsed": "notstarted"}
    match = _match(
        status=MatchStatus.SCHEDULED,
        kickoff_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    assert should_apply_game(game, match) is False


def test_should_skip_finished_without_change():
    game = {"finished": "TRUE", "time_elapsed": "finished", "home_score": "2", "away_score": "1"}
    match = _match(status=MatchStatus.FINISHED, home_score=2, away_score=1)
    assert should_apply_game(game, match) is False


def test_match_in_kickoff_window():
    now = datetime.now(timezone.utc)
    match = _match(status=MatchStatus.SCHEDULED, kickoff_at=now + timedelta(minutes=5))
    assert match_in_kickoff_window(match, now) is True


@pytest.mark.asyncio
async def test_rate_guard_blocks_when_over_threshold(monkeypatch):
    rate_mod._state.timestamps.clear()
    rate_mod._state.backoff_until = 0.0
    monkeypatch.setattr(rate_mod.settings, "worldcup_rate_limit_backoff_at", 2)
    monkeypatch.setattr(rate_mod.settings, "worldcup_rate_limit_warn_at", 1)
    rate_mod.record_request()
    rate_mod.record_request()
    assert rate_mod.can_request() is False


@pytest.mark.asyncio
async def test_poll_once_uses_batch_get_games(monkeypatch, setup_db):
    from app.db import async_session
    from app.services import worldcup_poller
    from app.services.live_poller import PollingWindow

    calls: list[str] = []

    class FakeClient:
        configured = True

        async def get_games(self):
            calls.append("games")
            return []

        async def get_game(self, _id):
            calls.append(f"game:{_id}")
            return None

    async def active_window(_db):
        return PollingWindow(active=True, in_live_window=True)

    async def fake_teams(_db):
        return {"1": object()}

    monkeypatch.setattr(worldcup_poller, "WorldCupApiClient", lambda: FakeClient())
    monkeypatch.setattr(worldcup_poller, "compute_polling_window", active_window)
    monkeypatch.setattr(worldcup_poller, "load_teams_by_seq", fake_teams)

    async def fake_code_map(_db):
        return {}

    async def fake_oid_map(_db):
        return {}

    monkeypatch.setattr(worldcup_poller, "build_code_map", fake_code_map)
    monkeypatch.setattr(worldcup_poller, "build_game_object_id_map", fake_oid_map)

    async with async_session() as db:
        interval = await poll_once(db)

    assert "games" in calls
    assert not any(c.startswith("game:") for c in calls)
    assert interval >= 25
