import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import async_session
from app.services.chat_context import build_chat_context
from app.services.groq_chat import chat_stream


async def main() -> None:
    msg = sys.argv[1] if len(sys.argv) > 1 else "Who are you"
    async with async_session() as db:
        ctx = await build_chat_context(db, msg, user=None)
        print("context_len", len(ctx))
        parts: list[str] = []
        async for p in chat_stream(ctx, msg, []):
            parts.append(p)
        print("chunks", len(parts))
        print("reply", "".join(parts)[:500])


if __name__ == "__main__":
    asyncio.run(main())
