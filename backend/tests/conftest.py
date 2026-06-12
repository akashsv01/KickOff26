import os

# Use SQLite for all tests - no Postgres/Docker required
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_kickoff26.db")
os.environ.setdefault("DATA_MODE", "mock")
os.environ.setdefault("LIVE_DATA_MODE", "demo")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("TESTING", "1")

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import async_session, init_db
from app.main import app
from app.services.data_ingestion import DataIngestionService
from app.services.match_lineups import clear_stored_lineups
from app.services.roster_seed import seed_team_rosters_from_bundle


@pytest.fixture(scope="session")
async def setup_db():
    """Create tables and seed mock data once per test session."""
    if os.path.exists("test_kickoff26.db"):
        os.remove("test_kickoff26.db")
    await init_db()
    async with async_session() as db:
        await DataIngestionService(db).sync_all(force=True)
        await clear_stored_lineups(db)
        await seed_team_rosters_from_bundle(db)
        await db.commit()


@pytest.fixture
async def client(setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client(client: AsyncClient):
    teams = (await client.get("/api/teams")).json()
    favorite_team_id = teams[0]["id"]
    res = await client.post(
        "/api/auth/register",
        json={
            "email": "test@kickoff26.dev",
            "username": "testfan",
            "password": "secret123",
            "favorite_team_id": favorite_team_id,
        },
    )
    if res.status_code == 400:
        res = await client.post(
            "/api/auth/login",
            json={"email": "test@kickoff26.dev", "password": "secret123"},
        )
    token = res.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
