"""Clear user-generated watch room content without touching tournament or account data."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bracket, Match, Message, Poll, PollVote, Room, Team, User


async def clear_room_user_content(db: AsyncSession) -> dict:
    """
    Remove all chat messages and poll votes, and reset reactions/polls on every room.

    Preserves rooms, matches, teams, users, brackets, and all other tables.
    """
    messages_deleted = (
        await db.execute(select(func.count()).select_from(Message))
    ).scalar_one()
    polls_deleted = (await db.execute(select(func.count()).select_from(Poll))).scalar_one()

    rooms = (await db.execute(select(Room))).scalars().all()
    rooms_reset = len(rooms)

    await db.execute(delete(Message))
    # Delete votes before polls so the wipe holds even where the FK cascade is
    # not enforced (e.g. SQLite without PRAGMA foreign_keys).
    await db.execute(delete(PollVote))
    await db.execute(delete(Poll))
    for room in rooms:
        room.reactions = {}
        room.polls = []
        room.active_poll = None

    return {
        "messages_deleted": messages_deleted,
        "polls_deleted": polls_deleted,
        "rooms_reset": rooms_reset,
    }


async def count_preserved_records(db: AsyncSession) -> dict:
    """Snapshot counts for verification after a reset."""
    return {
        "users": (await db.execute(select(func.count()).select_from(User))).scalar_one(),
        "teams": (await db.execute(select(func.count()).select_from(Team))).scalar_one(),
        "matches": (await db.execute(select(func.count()).select_from(Match))).scalar_one(),
        "brackets": (await db.execute(select(func.count()).select_from(Bracket))).scalar_one(),
        "rooms": (await db.execute(select(func.count()).select_from(Room))).scalar_one(),
        "messages": (await db.execute(select(func.count()).select_from(Message))).scalar_one(),
    }
