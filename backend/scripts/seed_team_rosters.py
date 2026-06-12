"""Seed team_rosters from bundled team_rosters_2026.json (no live Zafronix calls).

Usage:
    cd backend
    python scripts/seed_team_rosters.py
    python scripts/seed_team_rosters.py --force
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import async_session, init_db
from app.services.roster_seed import seed_team_rosters_from_bundle


async def main(force: bool) -> int:
    await init_db()
    async with async_session() as db:
        result = await seed_team_rosters_from_bundle(db, force=force)
        await db.commit()
    print(
        f"Roster seed: ready={result['ready']}/{result['teams']} "
        f"seeded={result['seeded']} unavailable={result['unavailable']}"
    )
    if result.get("missing"):
        print(f"Missing from bundle: {', '.join(result['missing'])}")
    return 0 if not result.get("missing") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed squads from team_rosters_2026.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing roster rows")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.force)))
