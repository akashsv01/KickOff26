"""Background Monte Carlo jobs — process pool, progress streaming, guardrails."""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.services.sim_worker import monte_carlo_worker
from app.services.simulator import sanitize_sim_result

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 50_000
SIM_TIMEOUT_SEC = 600
EXECUTOR_MAX_WORKERS = 2


class SimJobConflictError(Exception):
    """User already has a simulation running."""


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class SimJob:
    job_id: str
    user_key: str
    iterations: int
    mode: str  # live | quick
    channel: str
    status: JobStatus = JobStatus.QUEUED
    progress: dict[str, Any] = field(default_factory=lambda: {"done": 0, "total": 0})
    result: dict | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SimJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, SimJob] = {}
        self._user_active: dict[str, str] = {}
        self._executor: ProcessPoolExecutor | None = None
        self._manager: multiprocessing.managers.SyncManager | None = None
        self._lock = asyncio.Lock()

    def _ensure_manager(self) -> multiprocessing.managers.SyncManager:
        if self._manager is None:
            self._manager = multiprocessing.Manager()
        return self._manager

    def _ensure_executor(self) -> ProcessPoolExecutor:
        if self._executor is None:
            ctx = multiprocessing.get_context("spawn")
            self._executor = ProcessPoolExecutor(
                max_workers=EXECUTOR_MAX_WORKERS,
                mp_context=ctx,
            )
        return self._executor

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        if self._manager is not None:
            self._manager.shutdown()
            self._manager = None

    @staticmethod
    def validate_iterations(iterations: int) -> None:
        if iterations < 100:
            raise ValueError("iterations must be at least 100")
        if iterations > MAX_ITERATIONS:
            raise ValueError(f"iterations cannot exceed {MAX_ITERATIONS:,}")

    async def create_job(self, iterations: int, user_key: str, mode: str) -> SimJob:
        self.validate_iterations(iterations)
        from app.websocket.gateway import ws_manager

        async with self._lock:
            active_id = self._user_active.get(user_key)
            if active_id:
                active = self._jobs.get(active_id)
                if active and active.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                    raise SimJobConflictError(
                        "A simulation is already running. Wait for it to finish or try again later."
                    )

            job_id = str(uuid.uuid4())
            channel = ws_manager.simulation_channel(job_id)
            job = SimJob(
                job_id=job_id,
                user_key=user_key,
                iterations=iterations,
                mode=mode,
                channel=channel,
                progress={"done": 0, "total": iterations},
            )
            self._jobs[job_id] = job
            self._user_active[user_key] = job_id

        asyncio.create_task(self._execute_job(job))
        return job

    def get_job(self, job_id: str) -> SimJob | None:
        return self._jobs.get(job_id)

    async def _monitor_progress(
        self,
        job: SimJob,
        progress_queue: multiprocessing.Queue,
    ) -> None:
        from app.websocket.gateway import ws_manager

        while True:
            try:
                item = await asyncio.to_thread(progress_queue.get, True, 1.0)
            except Exception:
                if job.status != JobStatus.RUNNING:
                    break
                continue

            if item is None:
                break

            job.progress = {
                "done": item.get("done", 0),
                "total": item.get("total", job.iterations),
            }
            if job.mode != "live":
                continue

            payload: dict[str, Any] = {
                "type": "sim_progress",
                "done": job.progress["done"],
                "total": job.progress["total"],
            }
            if item.get("partial_champion") is not None:
                payload["partial_champion"] = item["partial_champion"]
            try:
                await ws_manager.broadcast(job.channel, payload)
            except Exception:
                logger.debug("WebSocket progress broadcast failed", exc_info=True)

    async def _execute_job(self, job: SimJob) -> None:
        from app.websocket.gateway import ws_manager

        job.status = JobStatus.RUNNING
        executor = self._ensure_executor()
        loop = asyncio.get_running_loop()
        progress_queue = self._ensure_manager().Queue()
        monitor = asyncio.create_task(self._monitor_progress(job, progress_queue))

        try:
            future = loop.run_in_executor(
                executor,
                monte_carlo_worker,
                job.iterations,
                None,
                progress_queue,
            )
            result = await asyncio.wait_for(future, timeout=SIM_TIMEOUT_SEC)
            result = sanitize_sim_result(result)
            job.result = result
            job.status = JobStatus.COMPLETE
            job.progress = {"done": job.iterations, "total": job.iterations}
            if job.mode == "live":
                await ws_manager.broadcast(
                    job.channel,
                    {"type": "sim_complete", "result": result},
                )
        except asyncio.TimeoutError:
            job.status = JobStatus.FAILED
            job.error = f"Simulation timed out after {SIM_TIMEOUT_SEC} seconds"
            logger.error("Simulation job %s timed out", job.job_id)
            if job.mode == "live":
                await ws_manager.broadcast(
                    job.channel,
                    {"type": "sim_error", "error": job.error},
                )
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc) or "Simulation failed"
            logger.exception("Simulation job %s failed", job.job_id)
            if job.mode == "live":
                await ws_manager.broadcast(
                    job.channel,
                    {"type": "sim_error", "error": job.error},
                )
        finally:
            try:
                progress_queue.put(None)
            except Exception:
                pass
            monitor.cancel()
            async with self._lock:
                if self._user_active.get(job.user_key) == job.job_id:
                    del self._user_active[job.user_key]


sim_job_manager = SimJobManager()
