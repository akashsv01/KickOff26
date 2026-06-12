"""Tests for DATABASE_URL normalization and one-shot database setup."""

import pytest

from app.database_url import build_connect_args, normalize_database_url
from app.db import async_session, engine, init_db
from app.services.database_setup import EXPECTED_TABLES, run_database_setup, verify_schema_sync


def test_normalize_neon_postgresql_url():
    raw = (
        "postgresql://user:secret@ep-example-pooler.us-east-1.aws.neon.tech/neondb"
        "?sslmode=require"
    )
    normalized = normalize_database_url(raw)
    assert normalized.startswith("postgresql+asyncpg://")
    assert "sslmode" not in normalized
    assert "ep-example-pooler.us-east-1.aws.neon.tech" in normalized

    ssl_args = build_connect_args(raw)
    assert "ssl" in ssl_args


def test_normalize_local_postgres_url():
    raw = "postgresql://postgres:admin123@localhost:5432/kickoff26"
    normalized = normalize_database_url(raw)
    assert normalized == "postgresql+asyncpg://postgres:admin123@localhost:5432/kickoff26"
    assert build_connect_args(raw) == {}


def test_normalize_sqlite_url():
    raw = "sqlite+aiosqlite:///./kickoff26.db"
    assert normalize_database_url(raw) == raw
    assert build_connect_args(raw) == {"check_same_thread": False}


@pytest.mark.asyncio
async def test_init_db_creates_full_schema(setup_db):
    async with engine.connect() as conn:
        schema = await conn.run_sync(verify_schema_sync)
    assert schema["ok"] is True
    assert not schema["missing"]
    for table in EXPECTED_TABLES:
        assert table in schema["tables"]


@pytest.mark.asyncio
async def test_setup_is_idempotent(setup_db):
    async with async_session() as db:
        first = await run_database_setup(db, skip_rosters=True, skip_worldcup=True)
        await db.commit()
    async with async_session() as db:
        second = await run_database_setup(db, skip_rosters=True, skip_worldcup=True)
        await db.commit()

    assert first.schema["ok"]
    assert second.schema["ok"]
    assert first.seed.get("teams", 0) >= 1
    assert second.seed.get("teams") == first.seed.get("teams")
    assert second.seed.get("matches") == first.seed.get("matches")
    assert first.user_content["users"] == 0
    assert first.user_content["messages"] == 0


@pytest.mark.asyncio
async def test_setup_module_cli_schema_only(setup_db):
    from app.setup import main

    code = await main(["--schema-only"])
    assert code == 0

    async with engine.connect() as conn:
        schema = await conn.run_sync(verify_schema_sync)
    assert schema["ok"]
