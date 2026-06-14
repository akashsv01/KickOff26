"""PATCH /api/users/me: a country change re-syncs the stored timezone, but an
explicit timezone is never overwritten - so profile + calendar always agree."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_country_change_resyncs_timezone(auth_client):
    r = await auth_client.patch("/api/users/me", json={"country": "India"})
    body = r.json()
    assert body["country"] == "India"
    assert body["timezone"] == "Asia/Kolkata"

    # Change country only (no timezone) -> stored zone re-syncs to the new country.
    r = await auth_client.patch("/api/users/me", json={"country": "United States"})
    body = r.json()
    assert body["country"] == "United States"
    assert body["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_explicit_timezone_is_not_overwritten(auth_client):
    # Country + explicit timezone in the same request -> explicit wins.
    r = await auth_client.patch(
        "/api/users/me", json={"country": "United States", "timezone": "America/Los_Angeles"}
    )
    assert r.json()["timezone"] == "America/Los_Angeles"

    # Later, change only the timezone -> saved; country unchanged.
    r = await auth_client.patch("/api/users/me", json={"timezone": "Europe/Paris"})
    body = r.json()
    assert body["timezone"] == "Europe/Paris"
    assert body["country"] == "United States"


@pytest.mark.asyncio
async def test_other_country_leaves_timezone_untouched(auth_client):
    await auth_client.patch("/api/users/me", json={"country": "Japan"})  # -> Asia/Tokyo
    r = await auth_client.patch("/api/users/me", json={"country": "Other"})
    body = r.json()
    assert body["country"] == "Other"
    assert body["timezone"] == "Asia/Tokyo"  # unmapped country: left for manual control
