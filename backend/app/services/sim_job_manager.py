"""Background Monte Carlo jobs - process pool, progress streaming, guardrails."""

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
STALE_QUEUED_SEC = 90
STALE_RUNNING_SEC = SIM_TIMEOUT_SEC + 60
EXECUTOR_MAX_WORKERS = 2


class SimJobConflictError(Exception):
    """A genuinely active simulation blocks this request (should be rare after replace)."""


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    started_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SimJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, SimJob] = {}
        self._user_active: dict[str, str] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._futures: dict[str, asyncio.Future] = {}
        self._executor: ProcessPoolExecutor | None = None
        self._manager: multiprocessing.managers.SyncManager | None = None
        self._lock = asyncio.Lock()

    def _touch(self, job: SimJob) -> None:
        job.updated_at = datetime.now(timezone.utc)

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
        for task in list(self._running_tasks.values()):
            task.cancel()
        self._running_tasks.clear()
        self._futures.clear()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        if self._manager is not None:
            self._manager.shutdown()
            self._manager = None
        self._user_active.clear()

    @staticmethod
    def validate_iterations(iterations: int) -> None:
        if iterations < 100:
            raise ValueError("iterations must be at least 100")
        if iterations > MAX_ITERATIONS:
            raise ValueError(f"iterations cannot exceed {MAX_ITERATIONS:,}")

    def _is_stale(self, job: SimJob) -> bool:
        if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
            return False
        now = datetime.now(timezone.utc)
        age = (now - job.created_at).total_seconds()
        idle = (now - job.updated_at).total_seconds()
        if job.status == JobStatus.QUEUED:
            return age > STALE_QUEUED_SEC
        if idle > STALE_RUNNING_SEC:
            return True
        if job.started_at and (now - job.started_at).total_seconds() > SIM_TIMEOUT_SEC + 30:
            return True
        return False

    async def _cancel_job(
        self,
        job: SimJob,
        *,
        reason: str,
        broadcast: bool = True,
    ) -> None:
        job.status = JobStatus.CANCELLED
        job.error = reason
        self._touch(job)

        task = self._running_tasks.pop(job.job_id, None)
        if task and not task.done():
            task.cancel()

        future = self._futures.pop(job.job_id, None)
        if future and not future.done():
            future.cancel()

        if broadcast and job.mode == "live":
            from app.websocket.gateway import ws_manager

            try:
                await ws_manager.broadcast(
                    job.channel,
                    {"type": "sim_error", "error": reason},
                )
            except Exception:
                logger.debug("WebSocket cancel broadcast failed", exc_info=True)

    async def _release_user_lock(self, user_key: str, job_id: str) -> None:
        async with self._lock:
            if self._user_active.get(user_key) == job_id:
                del self._user_active[user_key]

    async def _cancel_active_for_user(self, user_key: str, *, reason: str) -> None:
        async with self._lock:
            active_id = self._user_active.get(user_key)
            if not active_id:
                return
            active = self._jobs.get(active_id)
            if not active:
                del self._user_active[user_key]
                return
            if active.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                del self._user_active[user_key]
                return
            if self._is_stale(active):
                reason = "Previous simulation expired (stale lock cleared)"
            await self._cancel_job(active, reason=reason)
            if self._user_active.get(user_key) == active_id:
                del self._user_active[user_key]

    async def create_job(self, iterations: int, user_key: str, mode: str) -> SimJob:
        self.validate_iterations(iterations)
        from app.websocket.gateway import ws_manager

        await self._cancel_active_for_user(
            user_key,
            reason="Superseded by a new simulation run",
        )

        async with self._lock:
            active_id = self._user_active.get(user_key)
            if active_id:
                active = self._jobs.get(active_id)
                if active is None or active.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                    del self._user_active[user_key]
                elif self._is_stale(active):
                    await self._cancel_job(
                        active,
                        reason="Stale simulation lock cleared",
                        broadcast=False,
                    )
                    del self._user_active[user_key]
                else:
                    raise SimJobConflictError(
                        "A simulation is still starting. Wait a moment and try again."
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

        task = asyncio.create_task(self._execute_job(job))
        self._running_tasks[job_id] = task
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
                if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                    break
                continue

            if item is None:
                break

            job.progress = {
                "done": item.get("done", 0),
                "total": item.get("total", job.iterations),
            }
            self._touch(job)

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
        job.started_at = datetime.now(timezone.utc)
        self._touch(job)

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
            self._futures[job.job_id] = future
            result = await asyncio.wait_for(future, timeout=SIM_TIMEOUT_SEC)
            if job.status == JobStatus.CANCELLED:
                return
            result = sanitize_sim_result(result)
            job.result = result
            job.status = JobStatus.COMPLETE
            job.progress = {"done": job.iterations, "total": job.iterations}
            self._touch(job)
            if job.mode == "live":
                await ws_manager.broadcast(
                    job.channel,
                    {"type": "sim_complete", "result": result},
                )
        except asyncio.CancelledError:
            if job.status != JobStatus.CANCELLED:
                job.status = JobStatus.CANCELLED
                job.error = job.error or "Simulation cancelled"
                self._touch(job)
            raise
        except asyncio.TimeoutError:
            job.status = JobStatus.FAILED
            job.error = f"Simulation timed out after {SIM_TIMEOUT_SEC} seconds"
            self._touch(job)
            logger.error("Simulation job %s timed out", job.job_id)
            if job.mode == "live":
                await ws_manager.broadcast(
                    job.channel,
                    {"type": "sim_error", "error": job.error},
                )
        except Exception as exc:
            if job.status == JobStatus.CANCELLED:
                return
            job.status = JobStatus.FAILED
            job.error = str(exc) or "Simulation failed"
            self._touch(job)
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
            self._running_tasks.pop(job.job_id, None)
            self._futures.pop(job.job_id, None)
            await self._release_user_lock(job.user_key, job.job_id)


sim_job_manager = SimJobManager()
