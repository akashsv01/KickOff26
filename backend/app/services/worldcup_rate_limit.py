"""Sliding-window rate limit guard for the rezarahiminia API (500 req / 60s per IP)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitState:
    timestamps: deque[float] = field(default_factory=deque)
    backoff_until: float = 0.0
    last_429_at: float | None = None
    skipped_requests: int = 0


_state = RateLimitState()


def _window_seconds() -> int:
    return max(60, int(getattr(settings, "worldcup_rate_limit_window_seconds", 60)))


def _max_requests() -> int:
    return max(1, int(getattr(settings, "worldcup_rate_limit_per_minute", 500)))


def _warn_threshold() -> int:
    return int(getattr(settings, "worldcup_rate_limit_warn_at", 400))


def _backoff_threshold() -> int:
    return int(getattr(settings, "worldcup_rate_limit_backoff_at", 450))


def _prune(now: float) -> None:
    cutoff = now - _window_seconds()
    while _state.timestamps and _state.timestamps[0] < cutoff:
        _state.timestamps.popleft()


def requests_in_window() -> int:
    now = time.monotonic()
    _prune(now)
    return len(_state.timestamps)


def record_request() -> None:
    _state.timestamps.append(time.monotonic())


def record_429() -> None:
    now = time.monotonic()
    _state.last_429_at = now
    _state.backoff_until = now + _window_seconds()
    logger.warning(
        "WorldCup API 429 - backing off for %ss (requests in window=%s)",
        _window_seconds(),
        requests_in_window(),
    )


def can_request() -> bool:
    now = time.monotonic()
    if now < _state.backoff_until:
        return False
    _prune(now)
    count = len(_state.timestamps)
    if count >= _backoff_threshold():
        _state.skipped_requests += 1
        if _state.skipped_requests % 5 == 1:
            logger.warning(
                "WorldCup API rate guard: %s/%s requests in window - skipping call",
                count,
                _max_requests(),
            )
        return False
    if count >= _warn_threshold():
        logger.info(
            "WorldCup API rate guard: %s/%s requests in window - approaching limit",
            count,
            _max_requests(),
        )
    return True


async def wait_if_needed() -> bool:
    """Return True if a request may proceed, False if rate-limited."""
    if not can_request():
        return False
    count = requests_in_window()
    # Smooth bursts when above 70% of limit.
    if count > int(_max_requests() * 0.7):
        await asyncio.sleep(0.15)
    return can_request()


def get_rate_stats() -> dict:
    now = time.monotonic()
    _prune(now)
    count = len(_state.timestamps)
    return {
        "requests_in_window": count,
        "limit_per_window": _max_requests(),
        "window_seconds": _window_seconds(),
        "backoff_active": now < _state.backoff_until,
        "skipped_requests": _state.skipped_requests,
        "last_429_at": _state.last_429_at,
    }
