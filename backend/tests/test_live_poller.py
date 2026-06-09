"""Tests for live poller schedule logic and API event parsing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.live_poller import (
    INTERVAL_LIVE_BURST,
    INTERVAL_LIVE_DEFAULT,
    PollingWindow,
    next_poll_interval,
    trigger_burst,
    _state,
)
from app.services.matchday_alerts import diff_new_events, parse_api_events


def test_next_poll_interval_burst():
    _state.accelerated_until = datetime.now(timezone.utc) + timedelta(minutes=3)
    window = PollingWindow(active=True, in_live_window=True)
    assert next_poll_interval(window) == INTERVAL_LIVE_BURST
    _state.accelerated_until = None


def test_next_poll_interval_live_default():
    window = PollingWindow(active=True, in_live_window=True)
    assert next_poll_interval(window) == INTERVAL_LIVE_DEFAULT


def test_next_poll_interval_pre_kickoff():
    window = PollingWindow(active=True, in_live_window=False)
    assert next_poll_interval(window) == 180


def test_parse_api_events_goal_and_red_card():
    raw = [
        {
            "time": {"elapsed": 23},
            "team": {"id": 10},
            "player": {"name": "Player A"},
            "type": "Goal",
            "detail": "Normal Goal",
        },
        {
            "time": {"elapsed": 55},
            "team": {"id": 20},
            "player": {"name": "Player B"},
            "type": "Card",
            "detail": "Red Card",
        },
    ]
    events = parse_api_events(raw, api_home_id=10)
    assert len(events) == 2
    assert events[0]["type"] == "goal"
    assert events[0]["team"] == "home"
    assert events[1]["type"] == "red_card"
    assert events[1]["team"] == "away"


def test_diff_new_events():
    old = [{"type": "goal", "minute": 10, "team": "home", "player": "A"}]
    new = old + [{"type": "goal", "minute": 44, "team": "away", "player": "B"}]
    added = diff_new_events(old, new)
    assert len(added) == 1
    assert added[0]["minute"] == 44


def test_trigger_burst():
    trigger_burst()
    assert _state.accelerated_until is not None
    _state.accelerated_until = None
