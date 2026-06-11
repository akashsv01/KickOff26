from contextlib import asynccontextmanager
import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, bracket, chat, fanplan, matchday, rooms, teams
from app.config import settings
from app.db import async_session, init_db
from app.services.data_ingestion import DataIngestionService
from app.services.matchday import ensure_demo_live_match
from app.services.matchday_demo import run_demo_live_loop
from app.services.match_lineups import clear_stored_lineups
from app.services.roster_prefetch import run_roster_prefetch_loop
from app.services.worldcup_poller import bootstrap_worldcup_mode, run_worldcup_poller
from app.websocket.handler import router as ws_router

logger = logging.getLogger(__name__)
_live_task: asyncio.Task | None = None
_lineup_task: asyncio.Task | None = None
_roster_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _live_task, _lineup_task, _roster_task
    await init_db()
    async with async_session() as db:
        ingestion = DataIngestionService(db)
        await ingestion.sync_all(force=not settings.is_mock)

        cleared = await clear_stored_lineups(db)
        if cleared:
            logger.info("Cleared %s cached match lineup(s) — only API-sourced lineups are shown", cleared)

        if settings.is_demo_live:
            await ensure_demo_live_match(db)
            logger.info("LIVE_DATA_MODE=demo - live match ready (no API calls, no fabricated lineups)")
        elif settings.is_api_live:
            # Real data via the rezarahiminia World Cup 2026 API (lineups only when API publishes them).
            await bootstrap_worldcup_mode(db)
            logger.info(
                "LIVE_DATA_MODE=api - WorldCup26 reference synced, live poller will start"
            )

        await db.commit()

    if not os.environ.get("TESTING"):
        if settings.is_api_live:
            _live_task = asyncio.create_task(run_worldcup_poller())
        else:
            _live_task = asyncio.create_task(run_demo_live_loop())
        if settings.has_zafronix_key:
            _roster_task = asyncio.create_task(run_roster_prefetch_loop())

    yield

    from app.services.sim_job_manager import sim_job_manager
    from app.services.worldcup_api import close_shared_http_client

    sim_job_manager.shutdown()
    await close_shared_http_client()
    for task in (_live_task, _lineup_task, _roster_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="KickOff26 API",
    description="Companion API for the 2026 international football tournament",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(bracket.router, prefix="/api")
app.include_router(matchday.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(fanplan.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(ws_router)


@app.get("/health")
async def health():
    payload = {
        "status": "ok",
        "data_mode": settings.data_mode,
        "live_data_mode": settings.live_data_mode,
    }
    if settings.is_api_live:
        payload["live_source"] = "worldcup26.ir (rezarahiminia)"
        payload["worldcup_api_token_set"] = settings.has_worldcup_token
        from app.services.worldcup_api import WorldCupApiClient

        payload["worldcup_rate"] = WorldCupApiClient.rate_stats()
        payload["worldcup_poll_live_seconds"] = settings.worldcup_poll_live_seconds
    payload["zafronix_api_key_set"] = settings.has_zafronix_key
    payload["groq_assistant_configured"] = settings.has_groq_key
    return payload

