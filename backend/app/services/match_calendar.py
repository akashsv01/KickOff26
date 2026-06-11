"""Shared calendar-day bucketing for MatchDay (official schedule Eastern Time)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

# Official 2026 schedule PDF displays all times in Eastern Time (ET).
SCHEDULE_CALENDAR_TZ = ZoneInfo("America/New_York")


class HasLocalDate(Protocol):
    local_date: str | None


def calendar_date_from_kickoff(kickoff: datetime | None) -> str | None:
    if not kickoff:
        return None
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=ZoneInfo("UTC"))
    return kickoff.astimezone(SCHEDULE_CALENDAR_TZ).date().isoformat()


def match_calendar_date(match: HasLocalDate | dict) -> str | None:
    """Return YYYY-MM-DD calendar bucket (Eastern Time, per official schedule)."""
    if isinstance(match, dict):
        local = match.get("local_date")
        if local:
            return local
        kickoff = match.get("kickoff_at")
        if isinstance(kickoff, str):
            kickoff = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        return calendar_date_from_kickoff(kickoff)

    if match.local_date:
        return match.local_date
    kickoff = getattr(match, "kickoff_at", None)
    return calendar_date_from_kickoff(kickoff)


def summarize_match_days(matches: list) -> list[dict]:
    """Sorted dates with fixture counts - same logic used for badges and lists."""
    counts: dict[str, int] = {}
    for m in matches:
        key = match_calendar_date(m)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return [{"date": d, "match_count": counts[d]} for d in sorted(counts)]


def matches_on_date(matches: list, date_key: str) -> list:
    return [m for m in matches if match_calendar_date(m) == date_key]
