#!/usr/bin/env python3
"""Sync rezarahiminia World Cup 2026 API data into the local database.

Usage (from backend/):
    python scripts/sync_worldcup_api.py

Requires WORLDCUP_API_TOKEN and DATABASE_URL in .env.
Idempotent - safe to re-run (upserts by api_object_id).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import async_session, init_db
from app.services.worldcup_sync import sync_worldcup_data


async def main() -> None:
    await init_db()
    async with async_session() as db:
        result = await sync_worldcup_data(db)
        await db.commit()
    if not result.get("ok"):
        print(f"Sync failed: {result.get('error', result)}", file=sys.stderr)
        sys.exit(1)
    print("WorldCup API sync complete:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
