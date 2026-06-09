"""Shared WebSocket gateway for all real-time features."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Connection:
    websocket: Any
    user_id: int | None = None
    username: str = "guest"
    channels: set[str] = field(default_factory=set)


def parse_room_channel(channel: str) -> int | None:
    if not channel.startswith("room:"):
        return None
    try:
        return int(channel.split(":", 1)[1])
    except (IndexError, ValueError):
        return None


class WebSocketManager:
    """Single gateway for match updates, simulation progress, rooms, and alerts."""

    def __init__(self) -> None:
        self._connections: dict[str, Connection] = {}
        self._channel_subscribers: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, conn_id: str, websocket: Any, user_id: int | None = None, username: str = "guest") -> None:
        async with self._lock:
            self._connections[conn_id] = Connection(
                websocket=websocket, user_id=user_id, username=username
            )

    async def disconnect(self, conn_id: str) -> list[tuple[int, str]]:
        """Remove connection; return (room_id, username) pairs needing leave handling."""
        async with self._lock:
            conn = self._connections.pop(conn_id, None)
            if not conn:
                return []
            room_leaves: list[tuple[int, str]] = []
            for ch in list(conn.channels):
                if (room_id := parse_room_channel(ch)) is not None:
                    room_leaves.append((room_id, conn.username))
                subs = self._channel_subscribers.get(ch, set())
                subs.discard(conn_id)
            return room_leaves

    async def subscribe(self, conn_id: str, channel: str) -> None:
        async with self._lock:
            conn = self._connections.get(conn_id)
            if conn:
                conn.channels.add(channel)
                self._channel_subscribers.setdefault(channel, set()).add(conn_id)

    async def unsubscribe(self, conn_id: str, channel: str) -> tuple[int | None, str | None]:
        """Unsubscribe; return (room_id, username) when leaving a room channel."""
        async with self._lock:
            conn = self._connections.get(conn_id)
            username = conn.username if conn else None
            if conn:
                conn.channels.discard(channel)
            subs = self._channel_subscribers.get(channel, set())
            subs.discard(conn_id)
            room_id = parse_room_channel(channel)
            return room_id, username

    def room_participants(self, room_id: int) -> list[dict]:
        channel = self.room_channel(room_id)
        subs = self._channel_subscribers.get(channel, set())
        seen: set[str | int] = set()
        participants: list[dict] = []
        for conn_id in subs:
            conn = self._connections.get(conn_id)
            if not conn:
                continue
            dedupe_key: str | int = conn.user_id if conn.user_id is not None else conn_id
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            participants.append(
                {
                    "user_id": conn.user_id,
                    "username": conn.username,
                }
            )
        return participants

    def room_watcher_count(self, room_id: int) -> int:
        return len(self.room_participants(room_id))

    async def send_to(self, conn_id: str, message: dict) -> None:
        conn = self._connections.get(conn_id)
        if conn:
            try:
                await conn.websocket.send_json(message)
            except Exception:
                await self.disconnect(conn_id)

    async def broadcast(self, channel: str, message: dict) -> None:
        subs = list(self._channel_subscribers.get(channel, set()))
        for conn_id in subs:
            await self.send_to(conn_id, {**message, "channel": channel})

    async def broadcast_all(self, message: dict) -> None:
        for conn_id in list(self._connections.keys()):
            await self.send_to(conn_id, message)

    def room_channel(self, room_id: int) -> str:
        return f"room:{room_id}"

    def match_channel(self, match_id: int) -> str:
        return f"match:{match_id}"

    def user_channel(self, user_id: int) -> str:
        return f"user:{user_id}"

    def simulation_channel(self, task_id: str) -> str:
        return f"sim:{task_id}"


ws_manager = WebSocketManager()
