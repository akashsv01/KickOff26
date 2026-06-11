"""Tests for database schema integrity after migrations and seeding."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db import async_session
from app.services.db_integrity import verify_database_integrity


@pytest.mark.asyncio
async def test_seeded_database_passes_integrity_checks(setup_db):
    async with async_session() as db:
        issues = await verify_database_integrity(db)
    assert issues == [], "\n".join(issues)


@pytest.mark.asyncio
async def test_legacy_user_without_profile_fields_still_valid(setup_db, client: AsyncClient):
    from app.auth import hash_password
    from app.db import async_session
    from app.models import User

    async with async_session() as db:
        existing = (
            await db.execute(select(User).where(User.email == "legacy@kickoff26.dev"))
        ).scalar_one_or_none()
        if not existing:
            db.add(
                User(
                    email="legacy@kickoff26.dev",
                    username="legacyfan",
                    hashed_password=hash_password("secret123"),
                    followed_team_ids=[],
                )
            )
            await db.commit()

    login = await client.post(
        "/api/auth/login",
        json={"email": "legacy@kickoff26.dev", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = (
        await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()
    assert me["email"] == "legacy@kickoff26.dev"
    assert me["favorite_team_id"] is None
    assert me["country_region"] is None
    assert me["preferred_language"] is None
    assert isinstance(me["followed_team_ids"], list)


@pytest.mark.asyncio
async def test_register_with_profile_fields(client: AsyncClient):
    teams = (await client.get("/api/teams")).json()
    usa = next(t for t in teams if t["code"] == "USA")
    mex = next(t for t in teams if t["code"] == "MEX")

    res = await client.post(
        "/api/auth/register",
        json={
            "email": "fan@kickoff26.dev",
            "username": "worldcupfan",
            "password": "secret123",
            "favorite_team_id": usa["id"],
            "country_region": "United States",
            "preferred_language": "en",
            "followed_team_ids": [mex["id"]],
        },
    )
    assert res.status_code == 200, res.text
    user = res.json()["user"]
    assert user["favorite_team_id"] == usa["id"]
    assert user["country_region"] == "United States"
    assert user["preferred_language"] == "en"
    assert usa["id"] in user["followed_team_ids"]
    assert mex["id"] in user["followed_team_ids"]
