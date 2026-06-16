"""Durable fan-room poll aggregation + serialization.

Privacy boundary: aggregate counts and percentages are public (anyone in the
room sees them, and they go out over the WebSocket). An individual user's
selected option (``my_vote``) is only ever computed for - and returned to - that
one user. It is never included in a broadcast.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Poll, PollVote


def is_poll_closed(poll: Poll, *, now: datetime | None = None) -> bool:
    """A poll is closed if explicitly marked or its closes_at has passed."""
    if poll.closed:
        return True
    if poll.closes_at is not None:
        closes = poll.closes_at
        if closes.tzinfo is None:
            closes = closes.replace(tzinfo=timezone.utc)
        return (now or datetime.now(timezone.utc)) >= closes
    return False


def _percentages(counts: list[int], total: int) -> list[int]:
    """Whole-number percentages that sum to exactly 100 (largest-remainder)."""
    if total <= 0:
        return [0 for _ in counts]
    raw = [c * 100 / total for c in counts]
    floors = [int(r) for r in raw]
    leftover = 100 - sum(floors)
    # Hand the remaining points to the options with the largest fractional parts.
    order = sorted(range(len(counts)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:leftover]:
        floors[i] += 1
    return floors


def serialize_poll(poll: Poll, counts: list[int], my_vote: int | None) -> dict:
    """Build the public poll payload. ``my_vote`` is the caller's own option
    index (or None); pass None for broadcasts so no individual vote leaks."""
    options = list(poll.options or [])
    # Guard against any drift between stored options and aggregated counts.
    counts = (list(counts) + [0] * len(options))[: len(options)]
    total = sum(counts)
    pcts = _percentages(counts, total)
    return {
        "id": poll.id,
        "room_id": poll.room_id,
        "question": poll.question,
        "options": [
            {"index": i, "label": label, "votes": counts[i], "percentage": pcts[i]}
            for i, label in enumerate(options)
        ],
        "total_votes": total,
        "my_vote": my_vote,
        "created_by": poll.created_by or "",
        "created_at": poll.created_at.isoformat() if poll.created_at else None,
        "closes_at": poll.closes_at.isoformat() if poll.closes_at else None,
        "closed": is_poll_closed(poll),
    }


async def _counts_by_poll(db: AsyncSession, poll_ids: list[int]) -> dict[int, dict[int, int]]:
    if not poll_ids:
        return {}
    rows = await db.execute(
        select(PollVote.poll_id, PollVote.option_index, func.count())
        .where(PollVote.poll_id.in_(poll_ids))
        .group_by(PollVote.poll_id, PollVote.option_index)
    )
    out: dict[int, dict[int, int]] = {}
    for poll_id, option_index, count in rows.all():
        out.setdefault(poll_id, {})[option_index] = count
    return out


async def _my_votes(db: AsyncSession, poll_ids: list[int], user_id: int | None) -> dict[int, int]:
    if not poll_ids or user_id is None:
        return {}
    rows = await db.execute(
        select(PollVote.poll_id, PollVote.option_index).where(
            PollVote.poll_id.in_(poll_ids), PollVote.user_id == user_id
        )
    )
    return {poll_id: option_index for poll_id, option_index in rows.all()}


def _counts_list(poll: Poll, by_index: dict[int, int]) -> list[int]:
    return [by_index.get(i, 0) for i in range(len(poll.options or []))]


async def serialize_polls(
    db: AsyncSession, polls: list[Poll], *, user_id: int | None
) -> list[dict]:
    """Serialize many polls with two aggregate queries (counts + this user's votes)."""
    poll_ids = [p.id for p in polls]
    counts = await _counts_by_poll(db, poll_ids)
    mine = await _my_votes(db, poll_ids, user_id)
    return [
        serialize_poll(p, _counts_list(p, counts.get(p.id, {})), mine.get(p.id))
        for p in polls
    ]


async def load_room_polls(
    db: AsyncSession, room_id: int, *, user_id: int | None
) -> tuple[list[Poll], list[dict]]:
    """Newest-first polls for a room plus their serialized public payloads."""
    result = await db.execute(
        select(Poll)
        .where(Poll.room_id == room_id)
        .order_by(Poll.created_at.desc(), Poll.id.desc())
    )
    polls = list(result.scalars().all())
    return polls, await serialize_polls(db, polls, user_id=user_id)


async def serialize_one(db: AsyncSession, poll: Poll, *, user_id: int | None) -> dict:
    (payload,) = await serialize_polls(db, [poll], user_id=user_id)
    return payload
