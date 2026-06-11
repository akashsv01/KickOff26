"""Monte Carlo job manager - non-blocking execution and guardrails."""

from __future__ import annotations

import asyncio
import time

import pytest
from httpx import AsyncClient

from app.services.sim_job_manager import sim_job_manager


def assert_complete_sim_result(result: dict) -> None:
    """Champion probs sum ~100%, path populated, path champion = top marginal favorite."""
    champ_probs = result["team_stats"]["champion"]
    assert champ_probs
    assert abs(sum(champ_probs.values()) - 100) < 5

    top_code = next(iter(champ_probs))
    path = result["most_likely_path"]
    assert path.get("champion"), "most_likely_path.champion must be set"
    assert path["champion"] == top_code
    assert len(path.get("rounds") or []) == 4
    assert path["final"]["champion"] == top_code


async def _poll_until_complete(client: AsyncClient, task_id: str, timeout_sec: float = 120) -> dict:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        poll = await client.get(f"/api/bracket/simulate/jobs/{task_id}")
        assert poll.status_code == 200
        body = poll.json()
        if body["status"] == "complete":
            return body
        if body["status"] == "failed":
            pytest.fail(body.get("error", "simulation failed"))
        await asyncio.sleep(0.25)
    pytest.fail("simulation did not complete in time")


@pytest.fixture(autouse=True)
def _reset_sim_jobs():
    sim_job_manager._jobs.clear()
    sim_job_manager._user_active.clear()
    yield
    sim_job_manager.shutdown()
    sim_job_manager._manager = None


@pytest.mark.asyncio
async def test_quick_sim_returns_immediately_and_polls(client: AsyncClient):
    start = await client.post("/api/bracket/simulate/quick", json={"iterations": 500})
    assert start.status_code == 200
    task_id = start.json()["task_id"]
    assert start.json()["status"] in ("queued", "running")

    body = await _poll_until_complete(client, task_id)
    assert body["result"]["iterations"] == 500
    assert "champion" in body["result"]["team_stats"]
    assert_complete_sim_result(body["result"])


@pytest.mark.asyncio
async def test_live_sim_poll_returns_knockout_path(client: AsyncClient):
    """Live mode stores the same sanitized result as Quick (poll is source of truth)."""
    start = await client.post("/api/bracket/simulate", json={"iterations": 500})
    assert start.status_code == 200
    task_id = start.json()["task_id"]
    assert start.json()["channel"].startswith("sim:")

    body = await _poll_until_complete(client, task_id)
    assert body["result"]["iterations"] == 500
    assert_complete_sim_result(body["result"])


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["/api/bracket/simulate", "/api/bracket/simulate/quick"])
async def test_both_modes_return_valid_path_and_probs(client: AsyncClient, endpoint: str):
    start = await client.post(endpoint, json={"iterations": 400})
    assert start.status_code == 200
    body = await _poll_until_complete(client, start.json()["task_id"])
    assert_complete_sim_result(body["result"])


@pytest.mark.asyncio
async def test_health_stays_responsive_during_simulation(client: AsyncClient):
    start = await client.post("/api/bracket/simulate/quick", json={"iterations": 3000})
    assert start.status_code == 200
    task_id = start.json()["task_id"]

    for _ in range(5):
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        await asyncio.sleep(0.05)

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        poll = await client.get(f"/api/bracket/simulate/jobs/{task_id}")
        if poll.json()["status"] == "complete":
            return
        if poll.json()["status"] == "failed":
            pytest.fail(poll.json().get("error"))
        await asyncio.sleep(0.2)

    pytest.fail("simulation did not complete")


@pytest.mark.asyncio
async def test_simulation_runs_via_executor_not_inline():
    """Job must call loop.run_in_executor with monte_carlo_worker (not run_monte_carlo inline)."""
    calls: list[str] = []
    loop = asyncio.get_running_loop()
    original_run = loop.run_in_executor

    def tracking_run_in_executor(executor, fn, *args):
        calls.append(getattr(fn, "__name__", repr(fn)))
        return original_run(executor, fn, *args)

    loop.run_in_executor = tracking_run_in_executor  # type: ignore[method-assign]
    try:
        job = await sim_job_manager.create_job(150, "test:exec", mode="quick")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            j = sim_job_manager.get_job(job.job_id)
            if j and j.status.value in ("complete", "failed"):
                break
            await asyncio.sleep(0.1)
        assert j is not None
        assert j.status.value == "complete", j.error
        assert "monte_carlo_worker" in calls
    finally:
        loop.run_in_executor = original_run  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_rejects_overlapping_runs_for_same_user(client: AsyncClient):
    first = await client.post("/api/bracket/simulate/quick", json={"iterations": 2000})
    assert first.status_code == 200

    second = await client.post("/api/bracket/simulate/quick", json={"iterations": 500})
    assert second.status_code == 409

    task_id = first.json()["task_id"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        poll = await client.get(f"/api/bracket/simulate/jobs/{task_id}")
        if poll.json()["status"] == "complete":
            return
        await asyncio.sleep(0.2)

    pytest.fail("first simulation did not finish")


@pytest.mark.asyncio
async def test_rejects_iterations_above_cap(client: AsyncClient):
    res = await client.post("/api/bracket/simulate/quick", json={"iterations": 75000})
    assert res.status_code == 422
