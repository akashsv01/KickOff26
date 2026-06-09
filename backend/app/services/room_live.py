"""Live room helpers: presence broadcasts and join/leave system messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Room
from app.schemas import MessageResponse
from app.websocket.gateway import ws_manager


def new_poll_id() -> str:
    return uuid.uuid4().hex[:12]


def normalize_polls(room: Room) -> list[dict]:
    """Return polls list, migrating legacy active_poll when needed."""
    polls = list(room.polls or [])
    if not polls and room.active_poll:
        legacy = dict(room.active_poll)
        legacy.setdefault("id", new_poll_id())
        legacy.setdefault("votes", {})
        legacy.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        polls = [legacy]
    return polls


def serialize_poll(poll: dict) -> dict:
    return {
        "id": poll.get("id"),
        "question": poll.get("question", ""),
        "options": dict(poll.get("options") or {}),
        "votes": dict(poll.get("votes") or {}),
        "created_by": poll.get("created_by", ""),
        "created_at": poll.get("created_at"),
    }


def voter_key(user_id: int | None, guest_id: str | None) -> str:
    if user_id is not None:
        return f"user:{user_id}"
    gid = (guest_id or "anonymous").strip() or "anonymous"
    return f"guest:{gid}"


def apply_vote(poll: dict, option: str, key: str) -> dict:
    options = poll.setdefault("options", {})
    votes = poll.setdefault("votes", {})
    if option not in options:
        raise ValueError("Invalid option")
    prev = votes.get(key)
    if prev == option:
        return poll
    if prev and prev in options:
        options[prev] = max(0, int(options.get(prev, 0)) - 1)
    options[option] = int(options.get(option, 0)) + 1
    votes[key] = option
    return poll


async def broadcast_presence(room_id: int, match_id: int) -> None:
    participants = ws_manager.room_participants(room_id)
    payload = {
        "type": "presence_updated",
        "room_id": room_id,
        "match_id": match_id,
        "count": len(participants),
        "participants": participants,
    }
    await ws_manager.broadcast(ws_manager.room_channel(room_id), payload)
    await ws_manager.broadcast("watch:lobby", payload)


async def post_system_message(
    db: AsyncSession,
    room_id: int,
    content: str,
) -> MessageResponse:
    msg = Message(
        room_id=room_id,
        user_id=None,
        username="system",
        content=content,
        message_type="system",
    )
    db.add(msg)
    await db.flush()
    response = MessageResponse.model_validate(msg)
    await ws_manager.broadcast(
        ws_manager.room_channel(room_id),
        {"type": "new_message", "message": response.model_dump(mode="json")},
    )
    return response


async def on_room_join(
    db: AsyncSession,
    room_id: int,
    username: str,
) -> None:
    room = await db.get(Room, room_id)
    if not room:
        return
    await post_system_message(db, room_id, f"{username} joined")
    await broadcast_presence(room_id, room.match_id)


async def on_room_leave(
    db: AsyncSession,
    room_id: int,
    username: str,
) -> None:
    room = await db.get(Room, room_id)
    if not room:
        return
    await post_system_message(db, room_id, f"{username} left")
    await broadcast_presence(room_id, room.match_id)
