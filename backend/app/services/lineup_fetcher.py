"""Background lineup fetcher — one bundled API call per match at ~10 min pre-kickoff."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db import async_session
from app.services.api_football import ApiFootballClient, QuotaHalted
from app.services.match_lineups import fetch_and_store_lineup, matches_needing_lineup_fetch

logger = logging.getLogger(__name__)

TICK_SECONDS = 60


async def process_lineup_fetches(db) -> int:
    """Attempt lineup fetch for matches in the pre-kickoff window. Returns fetch count."""
    if not settings.is_api_live:
        return 0

    client = ApiFootballClient(db)
    if await client.is_halted():
        return 0

    matches = await matches_needing_lineup_fetch(db)
    fetched = 0
    for match in matches:
        try:
            if await fetch_and_store_lineup(db, match, client):
                fetched += 1
                logger.info(
                    "Stored lineup for match %s (fixture %s)",
                    match.id,
                    match.api_fixture_id,
                )
        except QuotaHalted:
            logger.warning("Lineup fetch halted — API quota low")
            break
    return fetched


async def run_lineup_fetcher() -> None:
    """Runs in API mode only; demo lineups are seeded at startup."""
    if not settings.is_api_live:
        return

    logger.info("Lineup fetcher started (bundled fixtures?id= at ~10 min pre-kickoff)")
    while True:
        await asyncio.sleep(TICK_SECONDS)
        async with async_session() as db:
            try:
                await process_lineup_fetches(db)
                await db.commit()
            except QuotaHalted:
                await db.rollback()
            except Exception as exc:
                logger.warning("Lineup fetch tick failed: %s", exc)
                await db.rollback()
