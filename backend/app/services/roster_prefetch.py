"""Background prefetch of stale Zafronix rosters (rate-limit friendly)."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db import async_session
from app.services.team_roster_service import prefetch_stale_rosters

logger = logging.getLogger(__name__)


async def run_roster_prefetch_loop() -> None:
    if not settings.has_zafronix_key:
        logger.info("Zafronix roster prefetch disabled (ZAFRONIX_API_KEY not set)")
        return

    logger.info("Zafronix roster prefetch loop started")
    while True:
        try:
            async with async_session() as db:
                count = await prefetch_stale_rosters(db, limit=2)
                await db.commit()
            if count:
                logger.debug("Zafronix prefetch synced %s roster(s)", count)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Zafronix roster prefetch failed: %s", exc)
        await asyncio.sleep(settings.zafronix_prefetch_interval_seconds)
