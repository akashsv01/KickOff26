import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings


async def main() -> None:
    base = settings.worldcup_api_base.rstrip("/")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.worldcup_api_token}",
    }
    for path in ("/get/teams", "/get/games"):
        url = f"{base}{path}"
        print("GET", url)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(url, headers=headers)
            print("  status", resp.status_code, "bytes", len(resp.content))
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    print("  list len", len(data))
                elif isinstance(data, dict):
                    print("  dict keys", list(data.keys())[:8])
                    for k in ("games", "matches", "data"):
                        if k in data and isinstance(data[k], list):
                            print(f"  {k} len", len(data[k]))
            else:
                print("  body", resp.text[:300])
        except Exception as exc:
            print("  exc", type(exc).__name__, repr(exc))
            if exc.__cause__:
                print("  cause", repr(exc.__cause__))


if __name__ == "__main__":
    asyncio.run(main())
