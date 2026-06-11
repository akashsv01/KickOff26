"""Groq API client (OpenAI-compatible) for the grounded tournament assistant."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are KickOff26's tournament assistant — a friendly, concise guide to the 2026 FIFA World Cup using ONLY the tournament data and user context provided below.

Rules:
- Answer ONLY using the provided TOURNAMENT DATA and USER CONTEXT. Never use outside knowledge or guess.
- If the answer is not in the data, say politely that you don't have that information in KickOff26's tournament data. Offer what you CAN help with (fixtures, standings, teams, squads, user's predictions).
- For personal questions, use ONLY what appears in USER CONTEXT (username, country from signup, followed teams, saved bracket). If not there, say the app doesn't have that information — never invent personal details.
- For off-topic questions (coding, general chat, other sports, opinions unrelated to the tournament), warmly decline and redirect: you help with 2026 tournament matches, teams, standings, and the user's predictions in KickOff26.
- For inappropriate or harmful requests, decline gracefully and redirect to the tournament.
- Be warm and helpful, not robotic. Use short paragraphs or bullet lists for fixtures and standings.
- Do not expose other users' data. Never claim to know the user's real name unless it equals their username in context.
- Tournament host cities and venues: only state what appears in fixture data.
- For "next match" or "today's matches", use the Schedule snapshot section (NEXT TOURNAMENT MATCH / LIVE NOW) — never pick the earliest date from the full fixture list or followed-team lists unless the user asked about their followed teams."""

FRIENDLY_UNAVAILABLE = (
    "I'm having trouble reaching the AI service right now. "
    "Please try again in a moment — or browse MatchDay and Standings in the app."
)

FRIENDLY_RATE_LIMIT = (
    "The assistant is a bit busy (rate limit). Please wait a few seconds and try again."
)

FRIENDLY_NOT_CONFIGURED = (
    "The KickOff26 assistant isn't configured on this server yet. "
    "An admin needs to set GROQ_API_KEY in the backend environment."
)

FRIENDLY_AUTH_FAILED = (
    "The assistant API key was rejected. "
    "Please check GROQ_API_KEY in backend/.env and restart the server."
)


def _model_id() -> str:
    model = (settings.groq_model or DEFAULT_MODEL).strip()
    return model or DEFAULT_MODEL


def _api_key() -> str:
    return settings.groq_api_key.strip()


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


def _build_messages(
    context: str,
    user_message: str,
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    system = f"{SYSTEM_PROMPT}\n\n--- TOURNAMENT DATA & USER CONTEXT ---\n{context}"
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for turn in history[-8:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _auth_error_message(status: int) -> str:
    if status in (401, 403):
        logger.error("Groq API auth failed (%s) — check GROQ_API_KEY and restart backend", status)
        return FRIENDLY_AUTH_FAILED
    return ""


async def chat_complete(context: str, user_message: str, history: list[dict[str, str]]) -> str:
    if not settings.has_groq_key:
        return FRIENDLY_NOT_CONFIGURED

    messages = _build_messages(context, user_message, history)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            resp = await client.post(
                f"{GROQ_BASE_URL.rstrip('/')}/chat/completions",
                headers=_headers(),
                json={
                    "model": _model_id(),
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": settings.groq_max_tokens,
                    "stream": False,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("Groq request failed: %s", exc)
        return FRIENDLY_UNAVAILABLE

    if resp.status_code == 429:
        return FRIENDLY_RATE_LIMIT
    if resp.status_code in (401, 403):
        return _auth_error_message(resp.status_code) or FRIENDLY_NOT_CONFIGURED
    if resp.status_code >= 400:
        logger.warning("Groq error %s: %s", resp.status_code, resp.text[:300])
        return FRIENDLY_UNAVAILABLE

    body = resp.json()
    choice = (body.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content")
    return (content or "").strip() or FRIENDLY_UNAVAILABLE


async def _groq_stream_tokens(
    messages: list[dict[str, str]],
    model: str,
) -> AsyncIterator[str]:
    """Yield text chunks from Groq streaming API, or raise on HTTP error."""
    url = f"{GROQ_BASE_URL.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": settings.groq_max_tokens,
        "stream": True,
    }
    timeout = httpx.Timeout(90.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, headers=_headers(), json=payload) as resp:
            if resp.status_code == 429:
                yield FRIENDLY_RATE_LIMIT
                return
            if resp.status_code in (401, 403):
                yield _auth_error_message(resp.status_code) or FRIENDLY_AUTH_FAILED
                return
            if resp.status_code >= 400:
                err_body = (await resp.aread()).decode(errors="replace")[:300]
                logger.warning("Groq stream error %s: %s", resp.status_code, err_body)
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text


async def chat_stream(
    context: str,
    user_message: str,
    history: list[dict[str, str]],
) -> AsyncIterator[str]:
    if not settings.has_groq_key:
        yield FRIENDLY_NOT_CONFIGURED
        return

    messages = _build_messages(context, user_message, history)
    model = _model_id()
    got_text = False

    try:
        async for piece in _groq_stream_tokens(messages, model):
            if piece in (FRIENDLY_RATE_LIMIT, FRIENDLY_AUTH_FAILED, FRIENDLY_NOT_CONFIGURED):
                yield piece
                return
            if piece:
                got_text = True
                yield piece
    except httpx.HTTPError as exc:
        logger.warning("Groq stream failed: %s", exc)
        yield FRIENDLY_UNAVAILABLE
        return

    if not got_text and model != FALLBACK_MODEL:
        try:
            async for piece in _groq_stream_tokens(messages, FALLBACK_MODEL):
                if piece in (FRIENDLY_RATE_LIMIT, FRIENDLY_AUTH_FAILED):
                    yield piece
                    return
                if piece:
                    got_text = True
                    yield piece
        except httpx.HTTPError as exc:
            logger.warning("Groq fallback stream failed: %s", exc)

    if not got_text:
        yield FRIENDLY_UNAVAILABLE
