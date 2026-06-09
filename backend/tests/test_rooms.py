import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_custom_poll_and_vote_change(auth_client: AsyncClient):
    matches = (await auth_client.get("/api/matchday/matches")).json()
    match_id = matches[0]["id"]
    room = (await auth_client.post("/api/rooms", json={"match_id": match_id})).json()
    room_id = room["id"]

    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={
                "question": "Best player tonight?",
                "options": ["Striker", "Midfielder", "Keeper"],
            },
        )
    ).json()
    assert poll["question"] == "Best player tonight?"
    assert len(poll["options"]) == 3

    voted = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll/vote",
            params={"option": "Striker", "poll_id": poll["id"]},
        )
    ).json()
    assert voted["options"]["Striker"] == 1
    assert voted["votes"]

    changed = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll/vote",
            params={"option": "Keeper", "poll_id": poll["id"]},
        )
    ).json()
    assert changed["options"]["Striker"] == 0
    assert changed["options"]["Keeper"] == 1


@pytest.mark.asyncio
async def test_room_summary(auth_client: AsyncClient):
    matches = (await auth_client.get("/api/matchday/matches")).json()
    match_id = matches[0]["id"]
    room = (await auth_client.post("/api/rooms", json={"match_id": match_id})).json()
    summary = (await auth_client.get("/api/rooms/summary")).json()
    assert any(s["match_id"] == match_id for s in summary)


@pytest.mark.asyncio
async def test_multiple_polls_newest_first(auth_client: AsyncClient):
    matches = (await auth_client.get("/api/matchday/matches")).json()
    match_id = matches[0]["id"]
    room = (await auth_client.post("/api/rooms", json={"match_id": match_id})).json()
    room_id = room["id"]

    await auth_client.post(
        f"/api/rooms/{room_id}/poll",
        json={"question": "First?", "options": ["A", "B"]},
    )
    await auth_client.post(
        f"/api/rooms/{room_id}/poll",
        json={"question": "Second?", "options": ["X", "Y"]},
    )
    detail = (await auth_client.get(f"/api/rooms/{room_id}")).json()
    assert detail["polls"][0]["question"] == "Second?"
    assert len(detail["polls"]) >= 2
