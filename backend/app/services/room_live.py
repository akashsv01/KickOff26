"""Live room helpers: presence broadcasts and join/leave system messages.

Poll persistence and aggregation now live in ``app.services.polls`` (durable
``polls`` / ``poll_votes`` tables); this module no longer handles polls.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Room
from app.schemas import MessageResponse
from app.websocket.gateway import ws_manager


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
