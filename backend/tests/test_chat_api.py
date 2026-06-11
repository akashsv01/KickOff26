"""Tests for chat API (no live Groq calls)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_status(client: AsyncClient):
    res = await client.get("/api/chat/status")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "model" in data


@pytest.mark.asyncio
async def test_chat_message_without_groq_key(client: AsyncClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "")
    res = await client.post(
        "/api/chat",
        json={"message": "Show Group A standings", "history": []},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is False
    assert "GROQ" in body["reply"] or "configured" in body["reply"].lower()
