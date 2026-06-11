"""Run database integrity checks (FK refs, official teams, user profile refs)."""

from __future__ import annotations

import asyncio
import sys

from app.db import async_session, init_db
from app.services.db_integrity import verify_database_integrity


async def main() -> int:
    await init_db()
    async with async_session() as db:
        issues = await verify_database_integrity(db)
    if issues:
        print("Database integrity issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print("Database integrity OK - all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
