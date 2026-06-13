"""Transactional email via the Resend REST API + fixtures helpers + welcome email.

Sending is best-effort and fail-safe: a missing key or a Resend error is logged
and swallowed so a failed email never blocks signup or a digest run. All content
is real (fixtures come from the DB). Branding/layout live in email_components and
are shared with the daily digest.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from zoneinfo import ZoneInfo

from app.config import settings
from app.data.country_timezones import resolve_timezone
from app.models import Match, MatchStatus, User
from app.services.email_components import (
    cta_button,
    empty_note,
    fmt_date_long,
    matches_section,
    paragraph,
    render_email,
    safe_zone,
    welcome_footer,
)

PASSWORD_RESET_TTL_MINUTES = 45

logger = logging.getLogger(__name__)

_RESEND_ENDPOINT = "https://api.resend.com/emails"

WELCOME_INTRO = (
    "Your companion for the 2026 World Cup - live scores, a prediction bracket, "
    "a travel planner, and real-time fan rooms, all in one place."
)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """POST one email to Resend. Returns True on success, False otherwise.

    Never raises - a missing RESEND_API_KEY or any transport/API error is logged
    and swallowed so callers (signup, digest job) are never blocked by email.
    """
    if not settings.has_resend_key:
        logger.warning("RESEND_API_KEY not set - skipping email to %s (%r)", to, subject)
        return False
    payload = {"from": settings.from_email, "to": [to], "subject": subject, "html": html_body}
    headers = {"Authorization": f"Bearer {settings.resend_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_RESEND_ENDPOINT, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("Resend send failed (%s) to %s: %s", resp.status_code, to, resp.text[:300])
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - email must never break the caller
        logger.exception("Resend send raised for %s: %s", to, exc)
        return False


# --------------------------------------------------------------------------- #
# Fixtures (real data; all windows computed in the user's timezone)
# --------------------------------------------------------------------------- #

def _aware_utc(dt: datetime | None) -> datetime | None:
    """Normalize a (possibly naive, e.g. SQLite) DB datetime to aware UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def matches_on_local_date(db: AsyncSession, zone: ZoneInfo, local_date: date) -> list[Match]:
    """All matches whose kickoff falls on ``local_date`` in ``zone`` (ordered)."""
    start_local = datetime.combine(local_date, time.min, tzinfo=zone)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = (start_local + timedelta(days=1)).astimezone(timezone.utc)
    rows = (
        await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(Match.kickoff_at.isnot(None))
            .where(Match.kickoff_at >= start_utc, Match.kickoff_at < end_utc)
            .order_by(Match.kickoff_at)
        )
    ).scalars().all()
    return rows


async def todays_matches_for_user(db: AsyncSession, user: User) -> tuple[ZoneInfo, list[Match]]:
    """(zone, matches) for the user's LOCAL today. Used by welcome + digest."""
    zone = safe_zone(resolve_timezone(user))
    today_local = datetime.now(zone).date()
    return zone, await matches_on_local_date(db, zone, today_local)


def first_kickoff_utc(matches: list[Match]) -> datetime | None:
    kickoffs = [_aware_utc(m.kickoff_at) for m in matches if m.kickoff_at is not None]
    return min(kickoffs) if kickoffs else None


async def tournament_bounds(db: AsyncSession) -> tuple[datetime | None, datetime | None]:
    """(first_kickoff_utc, last_kickoff_utc) across all fixtures, or (None, None)."""
    first = (
        await db.execute(
            select(Match).where(Match.kickoff_at.isnot(None)).order_by(Match.kickoff_at.asc()).limit(1)
        )
    ).scalar_one_or_none()
    last = (
        await db.execute(
            select(Match).where(Match.kickoff_at.isnot(None)).order_by(Match.kickoff_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return (_aware_utc(first.kickoff_at) if first else None, _aware_utc(last.kickoff_at) if last else None)


async def next_match_day(db: AsyncSession, zone: ZoneInfo, after_local_date: date) -> tuple[date, list[Match]] | None:
    """The next local date after ``after_local_date`` that has matches, and its matches."""
    after_end_local = datetime.combine(after_local_date, time.min, tzinfo=zone) + timedelta(days=1)
    after_end_utc = after_end_local.astimezone(timezone.utc)
    nxt = (
        await db.execute(
            select(Match)
            .where(Match.kickoff_at.isnot(None), Match.kickoff_at >= after_end_utc)
            .order_by(Match.kickoff_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if nxt is None or nxt.kickoff_at is None:
        return None
    nd = _aware_utc(nxt.kickoff_at).astimezone(zone).date()
    return nd, await matches_on_local_date(db, zone, nd)


async def first_match_day(db: AsyncSession, zone: ZoneInfo) -> tuple[date, list[Match]] | None:
    """The earliest match day overall (used before the tournament starts)."""
    first, _ = await tournament_bounds(db)
    if first is None:
        return None
    fd = first.astimezone(zone).date()
    return fd, await matches_on_local_date(db, zone, fd)


# --------------------------------------------------------------------------- #
# Welcome email (covers all signup-time scenarios)
# --------------------------------------------------------------------------- #

def _day_heading(label_date: date, today: date, zone: ZoneInfo) -> str:
    noon = datetime.combine(label_date, time(12, 0), tzinfo=zone)
    long = fmt_date_long(noon)
    if label_date == today:
        return f"Today - {long}"
    if label_date == today + timedelta(days=1):
        return f"Tomorrow - {long}"
    return f"Next up - {long}"


async def build_welcome_html(db: AsyncSession, user: User) -> str:
    """Branded welcome HTML covering all signup-time scenarios (1-6)."""
    zone = safe_zone(resolve_timezone(user))
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(zone)
    today = now_local.date()
    first_utc, last_utc = await tournament_bounds(db)

    sections = ""
    if first_utc is None:
        lead = "Fixtures will appear here as soon as they are announced."
    elif now_utc < first_utc:  # 5. tournament not started
        lead = f"The tournament kicks off on {fmt_date_long(first_utc.astimezone(zone))}."
        fd = await first_match_day(db, zone)
        if fd:
            fday, fmatches = fd
            sections = matches_section(_day_heading(fday, today, zone).replace("Next up", "Opening matches"), fmatches, zone, highlight_first=True)
    elif last_utc is not None and now_utc > last_utc + timedelta(hours=3):  # 6. concluded
        lead = "The tournament has concluded - thanks for following along!"
        sections = empty_note("Revisit the final standings and results any time.") + cta_button(
            "View standings", f"{settings.app_base_url.rstrip('/')}/standings"
        )
    else:  # in-tournament
        today_matches = await matches_on_local_date(db, zone, today)
        if not today_matches:  # 4. rest day
            lead = "No matches today - here is the next match day."
            nd = await next_match_day(db, zone, today)
            if nd:
                nday, nmatches = nd
                sections = matches_section(_day_heading(nday, today, zone), nmatches, zone, highlight_first=True)
            else:
                sections = empty_note("No upcoming matches are scheduled right now.")
        else:
            upcoming = [m for m in today_matches if m.status == MatchStatus.SCHEDULED]
            # 1/3: today (finished -> score, upcoming -> time)
            lead = "Here is what's on today." if upcoming else "Today's matches have wrapped - here's how they finished."
            sections = matches_section(_day_heading(today, today, zone), today_matches, zone, highlight_first=bool(upcoming))
            if not upcoming:  # 2: all finished -> add the next match day
                nd = await next_match_day(db, zone, today)
                if nd:
                    nday, nmatches = nd
                    sections += matches_section(_day_heading(nday, today, zone), nmatches, zone)

    body = paragraph(WELCOME_INTRO) + sections
    return render_email(
        preheader=lead,
        heading=f"Welcome to KickOff26, {user.username}!",
        subheading_html=f"{fmt_date_long(now_local)} &middot; {lead}",
        body_html=body,
        footer_html=welcome_footer(),
    )


async def send_password_reset_email(user_id: int, raw_token: str) -> bool:
    """Email a single-use password reset link (shared branded components).

    Best-effort: any error is logged and swallowed so the forgot-password
    endpoint never leaks whether an account exists via a send failure.
    """
    from app.db import async_session

    try:
        async with async_session() as db:
            user = await db.get(User, user_id)
            if not user:
                return False
            to_email, username = user.email, user.username
        link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={raw_token}"
        body = (
            paragraph(
                "We received a request to reset your KickOff26 password. Click the button "
                f"below to choose a new one. This link expires in {PASSWORD_RESET_TTL_MINUTES} "
                "minutes and can be used once."
            )
            + cta_button("Reset your password", link)
            + empty_note(
                "If you did not request this, you can safely ignore this email - your "
                "password will not change."
            )
        )
        html_body = render_email(
            preheader="Reset your KickOff26 password",
            heading="Password reset",
            subheading_html=f"Hi {username},",
            body_html=body,
            footer_html=welcome_footer(),
        )
        return await send_email(to_email, "Reset your KickOff26 password", html_body)
    except Exception as exc:  # noqa: BLE001 - never reveal existence via an error
        logger.exception("Password reset email failed for user %s: %s", user_id, exc)
        return False


async def send_welcome_email(user_id: int) -> bool:
    """Compose and send the welcome email. Opens its own session (BackgroundTasks-safe).

    Best-effort: any error is logged and swallowed, and the email degrades to a
    still-valid greeting + intro rather than failing, so signup is never affected.
    """
    from app.db import async_session

    try:
        async with async_session() as db:
            user = await db.get(User, user_id)
            if not user:
                return False
            to_email, username = user.email, user.username
            try:
                html_body = await build_welcome_html(db, user)
            except Exception as exc:  # noqa: BLE001 - degrade to a basic welcome
                logger.exception("Welcome fixtures failed for user %s, sending basic welcome: %s", user_id, exc)
                html_body = render_email(
                    preheader="Welcome to KickOff26",
                    heading=f"Welcome to KickOff26, {username}!",
                    subheading_html="Your 2026 World Cup companion.",
                    body_html=paragraph(WELCOME_INTRO),
                    footer_html=welcome_footer(),
                )
        return await send_email(to_email, "Welcome to KickOff26!", html_body)
    except Exception as exc:  # noqa: BLE001 - never break signup
        logger.exception("Welcome email failed for user %s: %s", user_id, exc)
        return False
