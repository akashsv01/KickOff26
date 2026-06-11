"""Tests for clearing watch-room user content without touching tournament data."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import async_session
from app.models import Bracket, Match, Message, Team, User
from app.services.room_reset import clear_room_user_content, count_preserved_records


@pytest.mark.asyncio
async def test_clear_room_user_content(auth_client: AsyncClient):
    matches = (await auth_client.get("/api/matchday/matches")).json()
    match_id = matches[0]["id"]
    room = (await auth_client.post("/api/rooms", json={"match_id": match_id})).json()
    room_id = room["id"]

    await auth_client.post(
        f"/api/rooms/{room_id}/messages",
        json={"content": "test: hyhy"},
    )
    await auth_client.post(
        f"/api/rooms/{room_id}/poll",
        json={"question": "Who wins?", "options": ["Home", "Away"]},
    )
    await auth_client.post(f"/api/rooms/{room_id}/reactions", params={"emoji": "🔥"})

    async with async_session() as db:
        before = await count_preserved_records(db)
        result = await clear_room_user_content(db)
        await db.commit()
        after = await count_preserved_records(db)

    assert result["messages_deleted"] >= 1
    assert result["rooms_reset"] >= 1
    assert after["messages"] == 0
    assert before["users"] == after["users"]
    assert before["teams"] == after["teams"]
    assert before["matches"] == after["matches"]
    assert before["brackets"] == after["brackets"]
    assert before["rooms"] == after["rooms"]

    detail = (await auth_client.get(f"/api/rooms/{room_id}")).json()
    assert detail["reactions"] == {}
    assert detail["polls"] == []
    assert detail["active_poll"] is None

    msgs = (await auth_client.get(f"/api/rooms/{room_id}/messages")).json()
    assert msgs == []


@pytest.mark.asyncio
async def test_reset_content_endpoint(auth_client: AsyncClient):
    matches = (await auth_client.get("/api/matchday/matches")).json()
    room = (await auth_client.post("/api/rooms", json={"match_id": matches[0]["id"]})).json()
    room_id = room["id"]
    await auth_client.post(
        f"/api/rooms/{room_id}/messages",
        json={"content": "hello"},
    )

    res = await auth_client.post("/api/rooms/reset-content")
    assert res.status_code == 200
    body = res.json()
    assert body["messages_deleted"] >= 1
    assert body["rooms_reset"] >= 1

    msgs = (await auth_client.get(f"/api/rooms/{room_id}/messages")).json()
    assert msgs == []


@pytest.mark.asyncio
async def test_room_features_work_after_reset(auth_client: AsyncClient):
    matches = (await auth_client.get("/api/matchday/matches")).json()
    room = (await auth_client.post("/api/rooms", json={"match_id": matches[0]["id"]})).json()
    room_id = room["id"]

    await auth_client.post("/api/rooms/reset-content")

    msg = (
        await auth_client.post(
            f"/api/rooms/{room_id}/messages",
            json={"content": "fresh start"},
        )
    ).json()
    assert msg["content"] == "fresh start"

    reactions = (
        await auth_client.post(f"/api/rooms/{room_id}/reactions", params={"emoji": "⚽"})
    ).json()
    assert reactions["⚽"] == 1

    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={"question": "Fresh poll?", "options": ["Yes", "No"]},
        )
    ).json()
    assert poll["question"] == "Fresh poll?"

    async with async_session() as db:
        users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        teams = (await db.execute(select(func.count()).select_from(Team))).scalar_one()
        match_count = (await db.execute(select(func.count()).select_from(Match))).scalar_one()
        brackets = (await db.execute(select(func.count()).select_from(Bracket))).scalar_one()
        messages = (await db.execute(select(func.count()).select_from(Message))).scalar_one()

    assert users >= 1
    assert teams >= 1
    assert match_count >= 1
    assert messages >= 1
