"""Opt-in daily digest email - polished, timezone-aware, idempotent.

For each opted-in user, in their own timezone, send one digest per local match
day roughly two hours before the first kickoff. ``send_due_digests`` is safe to
call every 15-30 minutes - it only sends inside the window and records the local
send date so a user is never emailed twice for the same day. Branding/layout are
shared with the welcome email via email_components (no duplication).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MatchStatus, User
from app.services.email_components import (
    fmt_date_long,
    fmt_date_short,
    matches_section,
    render_email,
    safe_zone,
    digest_footer,
)
from app.services.email_service import (
    _aware_utc,
    first_kickoff_utc,
    send_email,
    todays_matches_for_user,
)
from app.data.country_timezones import resolve_timezone

logger = logging.getLogger(__name__)

# Send the digest within this lead time before the day's first kickoff.
DIGEST_LEAD = timedelta(hours=2)


def _humanize_until(delta: timedelta) -> str:
    """'in about 2 hours' / 'in about 40 minutes' - derived from the real kickoff."""
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 1:
        return "very soon"
    if minutes < 60:
        return f"in about {minutes} minutes"
    hours = round(minutes / 60)
    return f"in about {hours} hour{'s' if hours != 1 else ''}"


async def build_daily_digest_html(db: AsyncSession, user: User) -> str | None:
    """Branded digest HTML for the user's local today, or None when there's nothing to send.

    Normal case: all of today's matches with zone-labeled kickoff times (first
    highlighted). Mixed case: any already-finished matches show their score. No
    matches today -> None (caller skips; never an empty digest).
    """
    zone = safe_zone(resolve_timezone(user))
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(zone)
    _, matches = await todays_matches_for_user(db, user)
    if not matches:
        return None  # safe no-op: never send an empty digest

    upcoming = [
        m
        for m in matches
        if m.status == MatchStatus.SCHEDULED and _aware_utc(m.kickoff_at) and _aware_utc(m.kickoff_at) > now_utc
    ]
    first_up = first_kickoff_utc(upcoming)
    if first_up is not None:
        lead = f"First match kicks off {_humanize_until(first_up - now_utc)} - here's your full day."
    else:
        lead = "Here's how today's matches are shaping up."

    body = matches_section("Today's matches", matches, zone, highlight_first=bool(upcoming))
    return render_email(
        preheader=lead,
        heading="Your KickOff26 Daily Digest",
        subheading_html=f"{fmt_date_long(now_local)} &middot; {lead}",
        body_html=body,
        footer_html=digest_footer(),
    )


async def build_daily_digest(db: AsyncSession, user: User) -> bool:
    """Compose and send today's digest for one user. Returns True only if sent."""
    html_body = await build_daily_digest_html(db, user)
    if html_body is None:
        return False
    subject = f"KickOff26 - Today's Matches ({fmt_date_short(datetime.now(safe_zone(resolve_timezone(user))))})"
    return await send_email(user.email, subject, html_body)


async def send_due_digests() -> dict:
    """Send digests to opted-in users ~2h before their first local kickoff.

    Idempotent per local date via ``users.last_digest_sent_date``. Because users
    span many timezones, call this frequently (every 15-30 min) so each user's
    window is hit in their own zone.
    """
    from app.db import async_session

    now_utc = datetime.now(timezone.utc)
    considered = sent = skipped = 0

    async with async_session() as db:
        users = (
            await db.execute(select(User).where(User.daily_digest_opt_in.is_(True)))
        ).scalars().all()

        for user in users:
            considered += 1
            try:
                zone, matches = await todays_matches_for_user(db, user)
                if not matches:
                    skipped += 1
                    continue

                today_local = datetime.now(zone).date()
                if user.last_digest_sent_date == today_local:
                    skipped += 1  # already sent today
                    continue

                first = first_kickoff_utc(matches)
                if first is None:
                    skipped += 1
                    continue

                # Only inside [first - 2h, first): not too early, not after kickoff.
                if not (first - DIGEST_LEAD <= now_utc < first):
                    skipped += 1
                    continue

                if await build_daily_digest(db, user):
                    user.last_digest_sent_date = today_local
                    sent += 1
                else:
                    skipped += 1  # send failed - retry on a later run, do not mark
            except Exception as exc:  # noqa: BLE001 - one bad user must not stop the run
                logger.exception("Digest failed for user %s: %s", user.id, exc)
                skipped += 1

        await db.commit()

    logger.info("Digest run: considered=%s sent=%s skipped=%s", considered, sent, skipped)
    return {"considered": considered, "sent": sent, "skipped": skipped}
