"""WebSocket endpoint handler."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import decode_token, get_user_by_id
from app.db import async_session
from app.services.room_live import on_room_join, on_room_leave
from app.websocket.gateway import parse_room_channel, ws_manager

router = APIRouter()


async def _resolve_user(token: str | None) -> tuple[int | None, str]:
    if not token:
        return None, "guest"
    uid = decode_token(token)
    if not uid:
        return None, "guest"
    async with async_session() as db:
        user = await get_user_by_id(db, uid)
        if user:
            return user.id, user.username
    return uid, f"user_{uid}"


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    conn_id = str(uuid.uuid4())
    token = websocket.query_params.get("token")
    user_id, username = await _resolve_user(token)

    await ws_manager.connect(conn_id, websocket, user_id=user_id, username=username)
    await ws_manager.send_to(conn_id, {"type": "connected", "conn_id": conn_id})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "subscribe":
                channel = data.get("channel", "")
                await ws_manager.subscribe(conn_id, channel)
                await ws_manager.send_to(conn_id, {"type": "subscribed", "channel": channel})

                room_id = parse_room_channel(channel)
                if room_id is not None:
                    async with async_session() as db:
                        await on_room_join(db, room_id, username)
                        await db.commit()

            elif msg_type == "unsubscribe":
                channel = data.get("channel", "")
                room_id, left_username = await ws_manager.unsubscribe(conn_id, channel)
                if room_id is not None and left_username:
                    async with async_session() as db:
                        await on_room_leave(db, room_id, left_username)
                        await db.commit()

            elif msg_type == "ping":
                await ws_manager.send_to(conn_id, {"type": "pong"})

    except WebSocketDisconnect:
        room_leaves = await ws_manager.disconnect(conn_id)
        for room_id, left_username in room_leaves:
            async with async_session() as db:
                await on_room_leave(db, room_id, left_username)
                await db.commit()
