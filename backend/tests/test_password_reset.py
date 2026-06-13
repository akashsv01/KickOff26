"""Tests for the forgot/reset-password flow and the signup digest opt-in."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.auth import hash_reset_token
from app.db import async_session
from app.models import User


async def _register(client, email: str, username: str, password: str, **extra):
    teams = (await client.get("/api/teams")).json()
    payload = {
        "email": email,
        "username": username,
        "password": password,
        "favorite_team_id": teams[0]["id"],
        **extra,
    }
    return await client.post("/api/auth/register", json=payload)


@pytest.mark.asyncio
async def test_forgot_password_is_generic_and_sets_token(client):
    # Unknown email -> same neutral response, no enumeration.
    r = await client.post("/api/auth/forgot-password", json={"email": "nobody@kickoff26.dev"})
    assert r.status_code == 200
    assert "reset link has been sent" in r.json()["detail"]

    await _register(client, "reset_set@kickoff26.dev", "resetset", "secret123")
    r = await client.post("/api/auth/forgot-password", json={"email": "reset_set@kickoff26.dev"})
    assert r.status_code == 200
    async with async_session() as db:
        u = (await db.execute(select(User).where(User.email == "reset_set@kickoff26.dev"))).scalar_one()
        assert u.password_reset_token_hash is not None
        assert u.password_reset_expires_at is not None


@pytest.mark.asyncio
async def test_reset_password_valid_then_single_use(client):
    await _register(client, "reset_flow@kickoff26.dev", "resetflow", "oldpass123")
    raw = "raw-token-for-reset-flow-123456"
    async with async_session() as db:
        u = (await db.execute(select(User).where(User.email == "reset_flow@kickoff26.dev"))).scalar_one()
        u.password_reset_token_hash = hash_reset_token(raw)
        u.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        await db.commit()

    r = await client.post("/api/auth/reset-password", json={"token": raw, "new_password": "newpass456"})
    assert r.status_code == 200

    # New password works.
    r = await client.post("/api/auth/login", json={"email": "reset_flow@kickoff26.dev", "password": "newpass456"})
    assert r.status_code == 200
    # Old password no longer works.
    r = await client.post("/api/auth/login", json={"email": "reset_flow@kickoff26.dev", "password": "oldpass123"})
    assert r.status_code == 401
    # Token is single-use.
    r = await client.post("/api/auth/reset-password", json={"token": raw, "new_password": "another789"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_invalid_and_expired(client):
    r = await client.post("/api/auth/reset-password", json={"token": "no-such-token", "new_password": "whatever123"})
    assert r.status_code == 400

    await _register(client, "reset_exp@kickoff26.dev", "resetexp", "oldpass123")
    raw = "expired-token-xyz"
    async with async_session() as db:
        u = (await db.execute(select(User).where(User.email == "reset_exp@kickoff26.dev"))).scalar_one()
        u.password_reset_token_hash = hash_reset_token(raw)
        u.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # expired
        await db.commit()
    r = await client.post("/api/auth/reset-password", json={"token": raw, "new_password": "newpass456"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_signup_persists_daily_digest_opt_in(client):
    r = await _register(
        client, "digest_signup@kickoff26.dev", "digestsignup", "secret123", daily_digest_opt_in=True
    )
    assert r.status_code == 200
    async with async_session() as db:
        u = (await db.execute(select(User).where(User.email == "digest_signup@kickoff26.dev"))).scalar_one()
        assert u.daily_digest_opt_in is True
