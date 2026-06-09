from contextlib import asynccontextmanager
import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, bracket, fanplan, matchday, rooms, teams
from app.config import settings
from app.db import async_session, init_db
from app.services.data_ingestion import DataIngestionService
from app.services.lineup_fetcher import run_lineup_fetcher
from app.services.live_poller import bootstrap_api_mode, run_live_poller
from app.services.matchday import ensure_demo_live_match
from app.services.matchday_demo import run_demo_live_loop
from app.services.match_lineups import ensure_demo_lineups
from app.websocket.handler import router as ws_router

logger = logging.getLogger(__name__)
_live_task: asyncio.Task | None = None
_lineup_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _live_task, _lineup_task
    await init_db()
    async with async_session() as db:
        ingestion = DataIngestionService(db)
        await ingestion.sync_all(force=not settings.is_mock)

        if settings.is_demo_live:
            seeded = await ensure_demo_lineups(db)
            await ensure_demo_live_match(db)
            logger.info(
                "LIVE_DATA_MODE=demo — %s demo lineups seeded, live match ready (no API calls)",
                seeded,
            )
        elif settings.is_api_live:
            await bootstrap_api_mode(db)
            logger.info("LIVE_DATA_MODE=api — fixture IDs linked, poller will start")

        await db.commit()

    if not os.environ.get("TESTING"):
        if settings.is_api_live:
            _live_task = asyncio.create_task(run_live_poller())
            _lineup_task = asyncio.create_task(run_lineup_fetcher())
        else:
            _live_task = asyncio.create_task(run_demo_live_loop())

    yield

    from app.services.sim_job_manager import sim_job_manager

    sim_job_manager.shutdown()
    for task in (_live_task, _lineup_task):
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
app.include_router(ws_router)


@app.get("/health")
async def health():
    payload = {
        "status": "ok",
        "data_mode": settings.data_mode,
        "live_data_mode": settings.live_data_mode,
    }
    if settings.is_api_live:
        async with async_session() as db:
            from app.services.api_football import ApiFootballClient

            payload["api_quota"] = await ApiFootballClient(db).get_quota_status()
    return payload

