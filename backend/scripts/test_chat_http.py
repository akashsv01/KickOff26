import asyncio
import json

import httpx


async def main() -> None:
    async with httpx.AsyncClient(timeout=120) as c:
        async with c.stream(
            "POST",
            "http://127.0.0.1:8000/api/chat/stream",
            json={"message": "Who are you", "history": []},
        ) as r:
            print("status", r.status_code)
            text = ""
            async for line in r.aiter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    text += json.loads(data).get("delta", "")
            print("reply:", text[:400])


if __name__ == "__main__":
    asyncio.run(main())
