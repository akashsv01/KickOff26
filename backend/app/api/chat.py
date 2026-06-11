"""Grounded tournament assistant chat API."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user
from app.config import settings
from app.db import get_db
from app.models import User
from app.services.chat_context import build_chat_context
from app.services.groq_chat import chat_complete, chat_stream

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    configured: bool


@router.get("/status")
async def chat_status():
    return {
        "configured": settings.has_groq_key,
        "model": settings.groq_model or "llama-3.3-70b-versatile",
    }


@router.post("", response_model=ChatResponse)
async def chat_message(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    context = await build_chat_context(db, body.message.strip(), user)
    history = [{"role": t.role, "content": t.content} for t in body.history]
    reply = await chat_complete(context, body.message.strip(), history)
    return ChatResponse(reply=reply, configured=settings.has_groq_key)


@router.post("/stream")
async def chat_stream_endpoint(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    context = await build_chat_context(db, body.message.strip(), user)
    history = [{"role": t.role, "content": t.content} for t in body.history]

    async def event_generator():
        async for delta in chat_stream(context, body.message.strip(), history):
            yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
