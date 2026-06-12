"""One-shot database bootstrap: schema + tournament data for fresh deployments."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import engine, init_db
from app.models import Bracket, Match, Message, Team, User
from app.services.data_ingestion import DataIngestionService
from app.services.db_integrity import verify_database_integrity
from app.services.team_roster_service import resync_all_rosters
from app.services.worldcup_sync import sync_worldcup_data

logger = logging.getLogger(__name__)

EXPECTED_TABLES: tuple[str, ...] = (
    "users",
    "teams",
    "team_rosters",
    "stadiums",
    "matches",
    "match_lineups",
    "match_events",
    "brackets",
    "rooms",
    "messages",
    "api_cache",
)


@dataclass
class SetupResult:
    schema: dict
    seed: dict = field(default_factory=dict)
    worldcup: dict = field(default_factory=dict)
    rosters: dict = field(default_factory=dict)
    integrity: list[str] = field(default_factory=list)
    user_content: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        if not self.schema.get("ok"):
            return False
        if settings.is_api_live and not self.worldcup.get("ok"):
            return False
        return not self.integrity


def verify_schema_sync(sync_conn) -> dict:
    """Ensure every expected table exists on the connected database."""
    insp = inspect(sync_conn)
    existing = set(insp.get_table_names())
    missing = [name for name in EXPECTED_TABLES if name not in existing]
    return {
        "ok": not missing,
        "tables": sorted(existing),
        "expected": list(EXPECTED_TABLES),
        "missing": missing,
    }


async def count_user_generated_content(db: AsyncSession) -> dict:
    """Counts that should be zero on a fresh production database."""
    return {
        "users": (await db.execute(select(func.count()).select_from(User))).scalar_one(),
        "brackets": (await db.execute(select(func.count()).select_from(Bracket))).scalar_one(),
        "messages": (await db.execute(select(func.count()).select_from(Message))).scalar_one(),
    }


async def run_database_setup(
    db: AsyncSession,
    *,
    skip_rosters: bool = False,
    skip_worldcup: bool = False,
) -> SetupResult:
    """
    Idempotent bootstrap for an empty or existing database.

    1. Create / migrate schema (init_db)
    2. Upsert openfootball teams + fixtures
    3. Upsert WorldCup API reference data (teams, stadiums, games, groups)
    4. Optionally prefetch Zafronix squads
    """
    await init_db()

    async with engine.connect() as conn:
        schema_report = await conn.run_sync(verify_schema_sync)

    seed = await DataIngestionService(db).sync_all(force=True)

    worldcup: dict = {"ok": True, "skipped": True}
    if not skip_worldcup:
        if settings.has_worldcup_token:
            worldcup = await sync_worldcup_data(db)
        elif settings.is_api_live:
            worldcup = {
                "ok": False,
                "skipped": True,
                "error": "WORLDCUP_API_TOKEN not set (required when LIVE_DATA_MODE=api)",
            }
        else:
            worldcup = {"ok": True, "skipped": True, "reason": "LIVE_DATA_MODE is not api"}

    rosters: dict = {"synced": 0, "skipped": True}
    if not skip_rosters and settings.has_zafronix_key:
        synced = await resync_all_rosters(db, force=False)
        rosters = {"synced": synced, "skipped": False}

    integrity = await verify_database_integrity(db)
    user_content = await count_user_generated_content(db)

    teams = (await db.execute(select(func.count()).select_from(Team))).scalar_one()
    matches = (await db.execute(select(func.count()).select_from(Match))).scalar_one()
    seed["teams"] = teams
    seed["matches"] = matches

    return SetupResult(
        schema=schema_report,
        seed=seed,
        worldcup=worldcup,
        rosters=rosters,
        integrity=integrity,
        user_content=user_content,
    )
