"""Decide which API game snapshots to apply during a poll cycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Match, MatchStatus
from app.services.live_poller import (
    MATCH_DURATION,
    POST_MATCH_BUFFER,
    PRE_KICKOFF_BUFFER,
)
from app.services.worldcup_parse import derive_status


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def match_in_kickoff_window(match: Match, now: datetime) -> bool:
    if match.status != MatchStatus.SCHEDULED:
        return False
    kickoff = _aware(match.kickoff_at)
    if kickoff is None:
        return False
    window_start = kickoff - PRE_KICKOFF_BUFFER
    window_end = kickoff + MATCH_DURATION + POST_MATCH_BUFFER
    return window_start <= now <= window_end


def should_apply_game(game: dict, match: Match, *, now: datetime | None = None) -> bool:
    """Apply only live, in-window scheduled, or transitioning matches - not far-future/finished."""
    now = now or datetime.now(timezone.utc)
    api_status = derive_status(game)

    if match.status == MatchStatus.LIVE:
        return True

    if match.status != api_status:
        return True

    if match.status == MatchStatus.SCHEDULED and match_in_kickoff_window(match, now):
        return True

    if match.status == MatchStatus.FINISHED:
        return False

    return False
