"""Tests for canonical MatchDay alert/event types."""

from app.services.matchday_alerts import (
    SUPPORTED_ALERT_TYPES,
    SUPPORTED_EVENT_TYPES,
    diff_new_events,
    filter_supported_events,
    parse_api_events,
)


def test_supported_event_types():
    assert SUPPORTED_EVENT_TYPES == frozenset(
        {"goal", "yellow_card", "red_card", "substitution", "penalty", "var"}
    )


def test_supported_alert_types():
    assert "match_halftime_alert" in SUPPORTED_ALERT_TYPES
    assert "momentum_alert" in SUPPORTED_ALERT_TYPES
    assert "corner_alert" not in SUPPORTED_ALERT_TYPES


def test_parse_api_events_ignores_corners_and_fouls():
    raw = [
        {"time": {"elapsed": 10}, "team": {"id": 1}, "type": "Corner", "detail": "Corner"},
        {"time": {"elapsed": 11}, "team": {"id": 1}, "type": "Foul", "detail": "Foul"},
        {
            "time": {"elapsed": 12},
            "team": {"id": 1},
            "player": {"name": "Jiménez"},
            "type": "Goal",
            "detail": "Normal Goal",
        },
    ]
    events = parse_api_events(raw, api_home_id=1)
    assert len(events) == 1
    assert events[0]["type"] == "goal"


def test_parse_penalty_and_var():
    raw = [
        {
            "time": {"elapsed": 55},
            "team": {"id": 2},
            "player": {"name": "B"},
            "type": "Goal",
            "detail": "Penalty",
        },
        {
            "time": {"elapsed": 60},
            "team": {"id": 1},
            "type": "Var",
            "detail": "Goal cancelled",
        },
    ]
    events = parse_api_events(raw, api_home_id=1)
    assert events[0]["type"] == "penalty"
    assert events[1]["type"] == "var"


def test_filter_supported_events():
    mixed = [
        {"type": "goal", "minute": 1},
        {"type": "corner", "minute": 2},
        {"type": "yellow_card", "minute": 3},
    ]
    assert len(filter_supported_events(mixed)) == 2


def test_diff_new_events():
    old = [{"type": "goal", "minute": 10, "team": "home", "player": "A", "detail": None}]
    new = old + [
        {"type": "substitution", "minute": 60, "team": "away", "player": "B", "detail": None}
    ]
    added = diff_new_events(old, new)
    assert len(added) == 1
    assert added[0]["type"] == "substitution"
