"""Picklable Monte Carlo worker entry point for ProcessPoolExecutor."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def monte_carlo_worker(
    iterations: int,
    seed: int | None,
    progress_queue: Any,
) -> dict:
    """
    Run Monte Carlo in a child process. Progress dicts are pushed to progress_queue;
    sends None sentinel when finished.
    """
    from app.services.simulator import run_monte_carlo

    def progress(done: int, total: int, partial_champion: dict | None = None) -> None:
        if progress_queue is None:
            return
        try:
            progress_queue.put(
                {
                    "done": done,
                    "total": total,
                    "partial_champion": partial_champion,
                }
            )
        except Exception:
            logger.debug("Progress queue full or closed", exc_info=True)

    try:
        return run_monte_carlo(iterations, seed, progress)
    except Exception:
        logger.exception("Monte Carlo worker failed (iterations=%s)", iterations)
        raise
    finally:
        if progress_queue is not None:
            try:
                progress_queue.put(None)
            except Exception:
                pass
