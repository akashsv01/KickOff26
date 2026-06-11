import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["data_mode"] == "mock"
    assert data["live_data_mode"] == "demo"


@pytest.mark.asyncio
async def test_list_teams(client: AsyncClient):
    res = await client.get("/api/teams")
    assert res.status_code == 200
    teams = res.json()
    assert len(teams) == 48


@pytest.mark.asyncio
async def test_list_matches(client: AsyncClient):
    res = await client.get("/api/matchday/matches")
    assert res.status_code == 200
    matches = res.json()
    assert len(matches) == 104
    assert "win_prob_home" in matches[0]


@pytest.mark.asyncio
async def test_bracket_groups(client: AsyncClient):
    res = await client.get("/api/bracket/groups")
    assert res.status_code == 200
    data = res.json()
    assert len(data["groups"]) == 12
    assert len(data["match_odds"]) > 0
    assert {t["code"] for t in data["groups"]["A"]} == {"MEX", "KOR", "RSA", "CZE"}
    assert {t["code"] for t in data["groups"]["B"]} == {"CAN", "SUI", "QAT", "BIH"}
    assert {t["code"] for t in data["groups"]["D"]} == {"USA", "PAR", "AUS", "TUR"}


@pytest.mark.asyncio
async def test_bracket_structure_group_fixtures(client: AsyncClient):
    res = await client.get("/api/bracket/structure")
    assert res.status_code == 200
    data = res.json()
    assert len(data["fixtures"]["C"]) == 6
    codes = set()
    for f in data["fixtures"]["C"]:
        codes.add(f["home"]["code"])
        codes.add(f["away"]["code"])
    assert codes == {"BRA", "MAR", "SCO", "HAI"}


@pytest.mark.asyncio
async def test_simulate_sync(client: AsyncClient):
    res = await client.post("/api/bracket/simulate/quick", json={"iterations": 200})
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    import asyncio
    import time

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        poll = await client.get(f"/api/bracket/simulate/jobs/{task_id}")
        assert poll.status_code == 200
        data = poll.json()
        if data["status"] == "complete":
            assert data["result"]["iterations"] == 200
            assert "champion" in data["result"]["team_stats"]
            assert "most_likely_path" in data["result"]
            assert data["result"]["most_likely_path"]["champion"] == next(
                iter(data["result"]["team_stats"]["champion"])
            )
            return
        await asyncio.sleep(0.15)
    pytest.fail("simulation did not complete")


@pytest.mark.asyncio
async def test_auth_and_follow(auth_client: AsyncClient):
    teams = (await auth_client.get("/api/teams")).json()
    team_ids = [teams[0]["id"], teams[1]["id"]]
    res = await auth_client.post("/api/teams/follow", json={"team_ids": team_ids})
    assert res.status_code == 200
    following = await auth_client.get("/api/matchday/following")
    assert following.status_code == 200


@pytest.mark.asyncio
async def test_fanplan_itinerary(auth_client: AsyncClient):
    teams = (await auth_client.get("/api/teams")).json()
    usa = next(t for t in teams if t["code"] == "USA")
    res = await auth_client.post(
        "/api/fanplan/itinerary",
        json={"team_ids": [usa["id"]], "max_cities": 4},
    )
    assert res.status_code == 200
    data = res.json()
    assert "stops" in data


@pytest.mark.asyncio
async def test_watch_room(auth_client: AsyncClient):
    matches = (await auth_client.get("/api/matchday/matches")).json()
    match_id = matches[0]["id"]
    room = await auth_client.post("/api/rooms", json={"match_id": match_id})
    assert room.status_code == 200
    room_id = room.json()["id"]
    msg = await auth_client.post(
        f"/api/rooms/{room_id}/messages",
        json={"content": "Let's go!"},
    )
    assert msg.status_code == 200
    messages = await auth_client.get(f"/api/rooms/{room_id}/messages")
    assert len(messages.json()) >= 1


@pytest.mark.asyncio
async def test_champion_poster(client: AsyncClient):
    res = await client.get("/api/bracket/poster/BRA")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_duplicate_username_rejected(client: AsyncClient):
    teams = (await client.get("/api/teams")).json()
    favorite = teams[0]["id"]
    await client.post(
        "/api/auth/register",
        json={
            "email": "a@test.com",
            "username": "dupeuser",
            "password": "secret123",
            "favorite_team_id": favorite,
        },
    )
    res = await client.post(
        "/api/auth/register",
        json={
            "email": "b@test.com",
            "username": "dupeuser",
            "password": "secret123",
            "favorite_team_id": favorite,
        },
    )
    assert res.status_code == 400
    assert "username" in res.json()["detail"].lower()
