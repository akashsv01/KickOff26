"""Standalone daily-digest runner (scheduler option b).

Run on a frequent schedule (every 15-30 min) so every user's "~2h before first
kickoff" window is hit in their own timezone. Idempotent - safe to run often.

Examples:
    python -m app.jobs.daily_digest

On DigitalOcean App Platform, configure a Scheduled Job with this command and a
cron like "*/15 * * * *". Requires RESEND_API_KEY + FROM_EMAIL in the env.
"""

from __future__ import annotations

import asyncio
import logging

from app.services.digest_service import send_due_digests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


async def main() -> int:
    summary = await send_due_digests()
    print(
        f"Digest run: considered={summary['considered']} "
        f"sent={summary['sent']} skipped={summary['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
