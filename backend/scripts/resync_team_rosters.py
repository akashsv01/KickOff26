"""Re-fetch Zafronix team rosters (live API — requires ZAFRONIX_LIVE_FETCH_ENABLED=true).

For normal re-seeding use scripts/seed_team_rosters.py instead (bundled JSON, no API calls).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import async_session, init_db
from app.services.team_roster_service import resync_all_rosters


async def main(force: bool) -> None:
    if not settings.zafronix_live_fetch:
        print("Set ZAFRONIX_LIVE_FETCH_ENABLED=true to use live Zafronix fetches.")
        print("For bundled squads run: python scripts/seed_team_rosters.py")
        return
    await init_db()
    async with async_session() as db:
        count = await resync_all_rosters(db, force=force)
        await db.commit()
    print(f"Synced {count} roster(s) from Zafronix live API (force={force})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Zafronix roster re-fetch (manual only)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh every team even if cache is still fresh",
    )
    args = parser.parse_args()
    asyncio.run(main(args.force))
