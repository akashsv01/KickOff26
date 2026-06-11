"""Clear watch-room chat, reactions, and polls while keeping all other data intact."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import async_session, init_db
from app.services.room_reset import clear_room_user_content, count_preserved_records


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset fan room messages, reactions, and polls to empty."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required flag — actually perform the reset.",
    )
    args = parser.parse_args()

    if not args.confirm:
        print("Dry run only. Re-run with --confirm to clear room content.")
        return 0

    db_label = (
        settings.database_url.split("@")[-1]
        if "@" in settings.database_url
        else settings.database_url
    )
    print(f"Database: {db_label}")

    await init_db()
    async with async_session() as db:
        before = await count_preserved_records(db)
        result = await clear_room_user_content(db)
        await db.commit()
        after = await count_preserved_records(db)

    print("Room content cleared:")
    print(f"  messages deleted: {result['messages_deleted']}")
    print(f"  rooms reset:      {result['rooms_reset']}")
    print("Preserved record counts (unchanged except messages -> 0):")
    for key in ("users", "teams", "matches", "brackets", "rooms"):
        print(f"  {key}: {before[key]} -> {after[key]}")
    print(f"  messages: {before['messages']} -> {after['messages']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
