"""Tests for shared email components + welcome/digest builders and send logic."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select

from app.db import async_session
from app.models import Match, MatchStatus, Team, User
from app.services import digest_service
from app.services.email_components import match_card, matches_section, render_email
from app.services.email_service import build_welcome_html


def _fake_match(status=MatchStatus.SCHEDULED, home_score=None, away_score=None):
    return SimpleNamespace(
        home_team=SimpleNamespace(name="Canada", code="CAN", flag_url="https://flagcdn.com/w80/ca.png"),
        away_team=SimpleNamespace(name="Mexico", code="MEX", flag_url="https://flagcdn.com/w80/mx.png"),
        status=status,
        home_score=home_score,
        away_score=away_score,
        minute=None,
        kickoff_at=datetime(2026, 6, 13, 18, 0, tzinfo=timezone.utc),
    )


def test_match_card_localizes_kickoff_and_zone_label():
    html = match_card(_fake_match(), ZoneInfo("Asia/Kolkata"))
    assert "Canada" in html and "Mexico" in html
    assert "CAN" in html and "MEX" in html
    assert "flagcdn.com/w80/ca.png" in html  # flag image (flags, not crests)
    assert "11:30 PM" in html and "IST" in html  # 18:00 UTC -> 23:30 IST, zone-labeled


def test_match_card_finished_shows_score():
    html = match_card(_fake_match(MatchStatus.FINISHED, 2, 1), ZoneInfo("UTC"))
    assert "2 - 1" in html
    assert "FT" in html


def test_matches_section_empty_is_blank():
    assert matches_section("Today", [], ZoneInfo("UTC")) == ""


def test_render_email_is_ip_safe_and_branded():
    html = render_email(
        preheader="x",
        heading="Hello",
        subheading_html="sub",
        body_html="body",
        footer_html="footer",
    )
    assert "FIFA" not in html
    assert "KickOff" in html  # original wordmark
    assert 'alt="KickOff26"' in html  # logo img with graceful alt fallback


@pytest.mark.asyncio
async def test_build_welcome_html_contains_greeting(setup_db):
    async with async_session() as db:
        user = User(
            email="welcome_html@kickoff26.dev",
            username="welcomehtml",
            hashed_password="x",
            timezone="Asia/Kolkata",
        )
        db.add(user)
        await db.commit()
        html = await build_welcome_html(db, user)
        assert "Welcome to KickOff26, welcomehtml!" in html
        assert "FIFA" not in html
        await db.delete(user)
        await db.commit()


@pytest.mark.asyncio
async def test_build_daily_digest_sends_when_matches_today(setup_db, monkeypatch):
    sent = AsyncMock(return_value=True)
    monkeypatch.setattr(digest_service, "send_email", sent)
    async with async_session() as db:
        teams = (await db.execute(select(Team).limit(2))).scalars().all()
        noon = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        match = Match(
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            status=MatchStatus.SCHEDULED,
            kickoff_at=noon,
            venue="Test Stadium",
            stage="group",
        )
        db.add(match)
        user = User(
            email="digest_build@kickoff26.dev",
            username="digestbuild",
            hashed_password="x",
            timezone="UTC",
            daily_digest_opt_in=True,
        )
        db.add(user)
        await db.commit()

        ok = await digest_service.build_daily_digest(db, user)
        assert ok is True
        assert sent.await_count == 1
        # subject is dated
        assert "Today's Matches" in sent.await_args.args[1]

        await db.delete(match)
        await db.delete(user)
        await db.commit()


@pytest.mark.asyncio
async def test_send_due_digests_skips_when_already_sent_today(setup_db, monkeypatch):
    sent = AsyncMock(return_value=True)
    monkeypatch.setattr(digest_service, "send_email", sent)
    async with async_session() as db:
        teams = (await db.execute(select(Team).limit(2))).scalars().all()
        noon = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        match = Match(
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            status=MatchStatus.SCHEDULED,
            kickoff_at=noon,
            venue="Test Stadium",
            stage="group",
        )
        db.add(match)
        user = User(
            email="digest_idem@kickoff26.dev",
            username="digestidem",
            hashed_password="x",
            timezone="UTC",
            daily_digest_opt_in=True,
            last_digest_sent_date=datetime.now(timezone.utc).date(),  # already sent today
        )
        db.add(user)
        await db.commit()
        match_id, user_id = match.id, user.id

    summary = await digest_service.send_due_digests()
    assert sent.await_count == 0  # idempotent: not re-sent same local day
    assert summary["sent"] == 0

    async with async_session() as db:
        await db.execute(delete(Match).where(Match.id == match_id))
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()
