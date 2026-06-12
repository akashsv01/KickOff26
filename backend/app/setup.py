"""CLI entrypoint: migrate schema + sync tournament data for fresh deployments.

Usage (from backend/):
    python -m app.setup
    python -m app.setup --skip-rosters
    python -m app.setup --schema-only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.config import settings
from app.database_url import database_url_label
from app.db import async_session, engine, init_db
from app.services.database_setup import run_database_setup, verify_schema_sync

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _print_result(result) -> None:
    schema = result.schema
    print(f"Schema: {len(schema.get('tables', []))} tables")
    if schema.get("missing"):
        print(f"  MISSING: {', '.join(schema['missing'])}")
    else:
        print("  All expected tables present")

    seed = result.seed
    print(
        f"Fixtures: teams={seed.get('teams', '?')} matches={seed.get('matches', '?')} "
        f"(source={seed.get('source', 'openfootball')})"
    )

    wc = result.worldcup
    if wc.get("skipped"):
        reason = wc.get("error") or wc.get("reason") or "skipped"
        print(f"WorldCup API: {reason}")
    else:
        print(
            f"WorldCup API: teams={wc.get('teams')} stadiums={wc.get('stadiums')} "
            f"games_mapped={wc.get('games_mapped')}"
        )

    rosters = result.rosters
    if rosters.get("skipped"):
        print("Zafronix rosters: skipped (no API key or --skip-rosters)")
    else:
        print(f"Zafronix rosters: synced {rosters.get('synced', 0)}")

    uc = result.user_content
    print(
        f"User content: users={uc.get('users')} brackets={uc.get('brackets')} "
        f"messages={uc.get('messages')}"
    )

    if result.integrity:
        print("Integrity issues:")
        for issue in result.integrity:
            print(f"  - {issue}")


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap KickOff26 database: schema + tournament data (idempotent)."
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Only create/migrate tables; skip data sync.",
    )
    parser.add_argument(
        "--skip-rosters",
        action="store_true",
        help="Skip Zafronix squad prefetch.",
    )
    parser.add_argument(
        "--skip-worldcup",
        action="store_true",
        help="Skip WorldCup API sync (openfootball seed only).",
    )
    args = parser.parse_args(argv)

    print(f"Database: {database_url_label(settings.database_url)}")
    print(f"DATA_MODE={settings.data_mode} LIVE_DATA_MODE={settings.live_data_mode}")

    if args.schema_only:
        await init_db()
        async with engine.connect() as conn:
            schema = await conn.run_sync(verify_schema_sync)
        if schema.get("missing"):
            print(f"Schema incomplete — missing: {', '.join(schema['missing'])}")
            return 1
        print(f"Schema OK ({len(schema['tables'])} tables)")
        return 0

    async with async_session() as db:
        result = await run_database_setup(
            db,
            skip_rosters=args.skip_rosters,
            skip_worldcup=args.skip_worldcup,
        )
        await db.commit()

    _print_result(result)

    if not result.ok:
        if result.worldcup.get("error"):
            logger.error(result.worldcup["error"])
        return 1

    print("Setup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
