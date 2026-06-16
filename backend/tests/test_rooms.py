import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db import async_session
from app.models import Poll


async def _new_room(auth_client: AsyncClient) -> int:
    matches = (await auth_client.get("/api/matchday/matches")).json()
    match_id = matches[0]["id"]
    room = (await auth_client.post("/api/rooms", json={"match_id": match_id})).json()
    return room["id"]


def _opt(poll: dict, index: int) -> dict:
    return next(o for o in poll["options"] if o["index"] == index)


async def _register_second_user(client: AsyncClient) -> str:
    teams = (await client.get("/api/teams")).json()
    res = await client.post(
        "/api/auth/register",
        json={
            "email": "second@kickoff26.dev",
            "username": "secondfan",
            "password": "secret123",
            "favorite_team_id": teams[0]["id"],
        },
        headers={"Authorization": ""},
    )
    if res.status_code == 400:
        res = await client.post(
            "/api/auth/login",
            json={"email": "second@kickoff26.dev", "password": "secret123"},
            headers={"Authorization": ""},
        )
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_create_poll_shape(auth_client: AsyncClient):
    room_id = await _new_room(auth_client)
    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={"question": "Best player tonight?", "options": ["Striker", "Midfielder", "Keeper"]},
        )
    ).json()
    assert poll["question"] == "Best player tonight?"
    assert [o["label"] for o in poll["options"]] == ["Striker", "Midfielder", "Keeper"]
    assert poll["total_votes"] == 0
    assert poll["my_vote"] is None
    assert poll["closed"] is False


@pytest.mark.asyncio
async def test_vote_change_updates_aggregate(auth_client: AsyncClient):
    room_id = await _new_room(auth_client)
    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={"question": "Who wins?", "options": ["Home", "Draw", "Away"]},
        )
    ).json()
    poll_id = poll["id"]

    voted = (
        await auth_client.post(f"/api/rooms/{room_id}/polls/{poll_id}/vote", json={"option": 0})
    ).json()
    assert voted["my_vote"] == 0
    assert _opt(voted, 0)["votes"] == 1
    assert voted["total_votes"] == 1
    assert _opt(voted, 0)["percentage"] == 100

    # Changing the vote moves the count - it does not add a second vote.
    changed = (
        await auth_client.post(f"/api/rooms/{room_id}/polls/{poll_id}/vote", json={"option": 2})
    ).json()
    assert changed["my_vote"] == 2
    assert _opt(changed, 0)["votes"] == 0
    assert _opt(changed, 2)["votes"] == 1
    assert changed["total_votes"] == 1


@pytest.mark.asyncio
async def test_votes_persist_and_my_vote_survives_rejoin(auth_client: AsyncClient):
    room_id = await _new_room(auth_client)
    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={"question": "Group winner?", "options": ["A", "B"]},
        )
    ).json()
    await auth_client.post(f"/api/rooms/{room_id}/polls/{poll['id']}/vote", json={"option": 1})

    # Simulate leaving and rejoining: a fresh fetch of the room + the polls list.
    room = (await auth_client.get(f"/api/rooms/{room_id}")).json()
    rejoined = room["polls"][0]
    assert rejoined["my_vote"] == 1
    assert _opt(rejoined, 1)["votes"] == 1

    polls = (await auth_client.get(f"/api/rooms/{room_id}/polls")).json()
    assert polls[0]["my_vote"] == 1
    assert polls[0]["total_votes"] == 1


@pytest.mark.asyncio
async def test_aggregate_across_users_but_my_vote_is_per_user(auth_client: AsyncClient, client: AsyncClient):
    room_id = await _new_room(auth_client)
    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={"question": "Pick one", "options": ["X", "Y"]},
        )
    ).json()
    poll_id = poll["id"]

    # First user (auth_client) votes X; second user votes Y.
    await auth_client.post(f"/api/rooms/{room_id}/polls/{poll_id}/vote", json={"option": 0})
    token2 = await _register_second_user(client)
    second = (
        await client.post(
            f"/api/rooms/{room_id}/polls/{poll_id}/vote",
            json={"option": 1},
            headers={"Authorization": f"Bearer {token2}"},
        )
    ).json()

    assert second["total_votes"] == 2
    assert _opt(second, 0)["votes"] == 1
    assert _opt(second, 1)["votes"] == 1
    assert second["my_vote"] == 1  # second user's own pick

    # First user still sees their own pick, and the shared aggregate.
    mine = (await auth_client.get(f"/api/rooms/{room_id}/polls")).json()[0]
    assert mine["my_vote"] == 0
    assert mine["total_votes"] == 2

    # Privacy: the payload exposes aggregates only - no per-user vote map / identities.
    assert "votes" not in mine or isinstance(mine.get("votes"), int) is False
    for option in mine["options"]:
        assert set(option.keys()) == {"index", "label", "votes", "percentage"}


@pytest.mark.asyncio
async def test_guest_cannot_vote(auth_client: AsyncClient, client: AsyncClient):
    room_id = await _new_room(auth_client)
    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={"question": "Auth gate?", "options": ["Yes", "No"]},
        )
    ).json()
    res = await client.post(
        f"/api/rooms/{room_id}/polls/{poll['id']}/vote",
        json={"option": 0},
        headers={"Authorization": ""},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_vote_on_closed_poll_rejected(auth_client: AsyncClient):
    room_id = await _new_room(auth_client)
    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={"question": "Closed soon?", "options": ["A", "B"]},
        )
    ).json()
    poll_id = poll["id"]

    async with async_session() as db:
        row = (await db.execute(select(Poll).where(Poll.id == poll_id))).scalar_one()
        row.closed = True
        await db.commit()

    res = await auth_client.post(f"/api/rooms/{room_id}/polls/{poll_id}/vote", json={"option": 0})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_invalid_option_rejected(auth_client: AsyncClient):
    room_id = await _new_room(auth_client)
    poll = (
        await auth_client.post(
            f"/api/rooms/{room_id}/poll",
            json={"question": "Range check", "options": ["A", "B"]},
        )
    ).json()
    res = await auth_client.post(
        f"/api/rooms/{room_id}/polls/{poll['id']}/vote", json={"option": 5}
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_room_summary(auth_client: AsyncClient):
    matches = (await auth_client.get("/api/matchday/matches")).json()
    match_id = matches[0]["id"]
    await auth_client.post("/api/rooms", json={"match_id": match_id})
    summary = (await auth_client.get("/api/rooms/summary")).json()
    assert any(s["match_id"] == match_id for s in summary)


@pytest.mark.asyncio
async def test_multiple_polls_newest_first(auth_client: AsyncClient):
    room_id = await _new_room(auth_client)
    await auth_client.post(f"/api/rooms/{room_id}/poll", json={"question": "First?", "options": ["A", "B"]})
    await auth_client.post(f"/api/rooms/{room_id}/poll", json={"question": "Second?", "options": ["X", "Y"]})
    detail = (await auth_client.get(f"/api/rooms/{room_id}")).json()
    assert detail["polls"][0]["question"] == "Second?"
    assert len(detail["polls"]) >= 2
