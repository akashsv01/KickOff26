"""Re-fetch all Zafronix team rosters (cache bust after position-mapping fixes).

Usage:
    cd backend
    python scripts/resync_team_rosters.py
    python scripts/resync_team_rosters.py --force
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import async_session, init_db
from app.services.team_roster_service import resync_all_rosters


async def main(force: bool) -> None:
    await init_db()
    async with async_session() as db:
        count = await resync_all_rosters(db, force=force)
        await db.commit()
    print(f"Synced {count} roster(s) from Zafronix (force={force})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-fetch Zafronix team rosters")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh every team even if cache is still fresh",
    )
    args = parser.parse_args()
    asyncio.run(main(args.force))
