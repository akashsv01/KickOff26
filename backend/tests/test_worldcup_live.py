"""Tests for real-API live apply, alert gating, and demo reset."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Match, MatchEvent, MatchStatus
from app.services.worldcup_live import apply_game_snapshot, build_code_map, build_game_object_id_map
from app.services.worldcup_reset import reset_demo_fabrication_for_api_mode
from app.services.worldcup_sync import upsert_games, upsert_stadiums, upsert_teams
from tests.test_worldcup_mapping import (
    SAMPLE_GAME,
    SAMPLE_STADIUM,
    SAMPLE_TEAM_AUS,
    SAMPLE_TEAM_TUR,
)


@pytest.mark.asyncio
async def test_reset_clears_demo_live_match(setup_db):
    from app.db import async_session
    from app.services.fixtures_loader import opening_match_external_id
    from app.services.matchday import ensure_demo_live_match

    async with async_session() as db:
        await ensure_demo_live_match(db)
        await db.commit()

    async with async_session() as db:
        live = (
            await db.execute(select(Match).where(Match.status == MatchStatus.LIVE))
        ).scalars().all()
        assert len(live) == 1
        opening = (
            await db.execute(select(Match).where(Match.external_id == opening_match_external_id()))
        ).scalar_one()
        assert opening.home_score == 2

    async with async_session() as db:
        stats = await reset_demo_fabrication_for_api_mode(db)
        await db.commit()
        assert stats["live_matches_reset"] >= 1

        live = (
            await db.execute(select(Match).where(Match.status == MatchStatus.LIVE))
        ).scalars().all()
        assert live == []
        opening = (
            await db.execute(select(Match).where(Match.external_id == opening_match_external_id()))
        ).scalar_one()
        assert opening.home_score is None
        events = (
            await db.execute(select(MatchEvent).where(MatchEvent.match_id == opening.id))
        ).scalars().all()
        assert events == []


@pytest.mark.asyncio
async def test_apply_snapshot_goal_and_status_alerts_only_from_real_diff(setup_db, monkeypatch):
    from app.db import async_session

    alerts: list[dict] = []

    async def capture_alert(alert, match_id):
        alerts.append({"alert": alert, "match_id": match_id})

    monkeypatch.setattr("app.services.matchday_alerts.broadcast_alert", capture_alert)
    monkeypatch.setattr("app.services.worldcup_live.broadcast_alert", capture_alert)
    monkeypatch.setattr("app.services.worldcup_live.emit_prob_momentum", AsyncMock())

    async with async_session() as db:
        teams_by_seq = await upsert_teams(db, [SAMPLE_TEAM_AUS, SAMPLE_TEAM_TUR])
        stadiums_by_seq = await upsert_stadiums(db, [SAMPLE_STADIUM])
        await upsert_games(
            db,
            [SAMPLE_GAME],
            teams_by_seq=teams_by_seq,
            stadiums_by_seq=stadiums_by_seq,
        )
        match = (
            await db.execute(
                select(Match)
                .options(selectinload(Match.home_team), selectinload(Match.away_team))
                .where(Match.api_object_id == SAMPLE_GAME["_id"])
            )
        ).scalar_one()
        match.status = MatchStatus.SCHEDULED
        match.home_score = None
        match.away_score = None
        match.minute = None
        await db.commit()

    async with async_session() as db:
        code_map = await build_code_map(db)
        oid_map = await build_game_object_id_map(db)
        teams_by_seq = await upsert_teams(db, [SAMPLE_TEAM_AUS, SAMPLE_TEAM_TUR])
        match = (
            await db.execute(
                select(Match)
                .options(selectinload(Match.home_team), selectinload(Match.away_team))
                .where(Match.api_object_id == SAMPLE_GAME["_id"])
            )
        ).scalar_one()

        await apply_game_snapshot(
            db,
            {**SAMPLE_GAME, "time_elapsed": "live", "home_score": "0", "away_score": "0"},
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=True,
        )
        await db.commit()

        alert_types = [a["alert"]["type"] for a in alerts]
        assert "match_start_alert" in alert_types
        assert "yellow_card_alert" not in alert_types
        assert "substitution_alert" not in alert_types

        alerts.clear()
        await apply_game_snapshot(
            db,
            {
                **SAMPLE_GAME,
                "time_elapsed": "23",
                "home_score": "1",
                "away_score": "0",
                "home_scorers": '[{"scorer":"Smith","minute":"23"}]',
            },
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=True,
        )
        await db.commit()

        alert_types = [a["alert"]["type"] for a in alerts]
        assert "goal_alert" in alert_types
        assert match.home_score == 1

        alerts.clear()
        monkeypatch.setattr("app.services.worldcup_live.emit_prob_momentum", AsyncMock())
        await apply_game_snapshot(
            db,
            {
                **SAMPLE_GAME,
                "time_elapsed": "24",
                "home_score": "1",
                "away_score": "0",
                "home_scorers": '[{"scorer":"Smith","minute":"23"}]',
            },
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=True,
        )
        assert alerts == []


@pytest.mark.asyncio
async def test_no_broadcast_when_snapshot_unchanged(setup_db, monkeypatch):
    from app.db import async_session

    broadcasts: list[int] = []

    async def capture_broadcast(channel, payload):
        broadcasts.append(payload.get("match", {}).get("id"))

    monkeypatch.setattr("app.services.worldcup_live.ws_manager.broadcast", capture_broadcast)
    monkeypatch.setattr("app.services.matchday_alerts.broadcast_alert", AsyncMock())
    monkeypatch.setattr("app.services.worldcup_live.emit_prob_momentum", AsyncMock())

    async with async_session() as db:
        teams_by_seq = await upsert_teams(db, [SAMPLE_TEAM_AUS, SAMPLE_TEAM_TUR])
        stadiums_by_seq = await upsert_stadiums(db, [SAMPLE_STADIUM])
        await upsert_games(
            db,
            [SAMPLE_GAME],
            teams_by_seq=teams_by_seq,
            stadiums_by_seq=stadiums_by_seq,
        )
        code_map = await build_code_map(db)
        oid_map = await build_game_object_id_map(db)
        live_game = {**SAMPLE_GAME, "time_elapsed": "10", "home_score": "1", "away_score": "0"}

        await apply_game_snapshot(
            db,
            live_game,
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=True,
        )
        broadcasts.clear()

        await apply_game_snapshot(
            db,
            live_game,
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=True,
        )
        assert broadcasts == []


@pytest.mark.asyncio
async def test_prob_momentum_only_on_score_change(setup_db, monkeypatch):
    from app.db import async_session
    from app.services import worldcup_live

    momentum_calls: list[tuple] = []

    async def track_momentum(match, old_probs, new_probs):
        momentum_calls.append((old_probs, new_probs))

    monkeypatch.setattr(worldcup_live, "emit_prob_momentum", track_momentum)
    monkeypatch.setattr("app.services.matchday_alerts.broadcast_alert", AsyncMock())

    async with async_session() as db:
        teams_by_seq = await upsert_teams(db, [SAMPLE_TEAM_AUS, SAMPLE_TEAM_TUR])
        stadiums_by_seq = await upsert_stadiums(db, [SAMPLE_STADIUM])
        await upsert_games(
            db,
            [SAMPLE_GAME],
            teams_by_seq=teams_by_seq,
            stadiums_by_seq=stadiums_by_seq,
        )
        match = (
            await db.execute(select(Match).where(Match.api_object_id == SAMPLE_GAME["_id"]))
        ).scalar_one()
        match.status = MatchStatus.SCHEDULED
        match.home_score = None
        match.away_score = None
        match.minute = None
        code_map = await build_code_map(db)
        oid_map = await build_game_object_id_map(db)
        live_game = {**SAMPLE_GAME, "time_elapsed": "10", "home_score": "1", "away_score": "0"}
        await apply_game_snapshot(
            db,
            live_game,
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=True,
        )
        assert len(momentum_calls) == 1

        momentum_calls.clear()
        await apply_game_snapshot(
            db,
            {**live_game, "time_elapsed": "11"},
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=True,
        )
        assert momentum_calls == []

        momentum_calls.clear()
        await apply_game_snapshot(
            db,
            {**live_game, "time_elapsed": "12", "home_score": "2", "away_score": "0"},
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=True,
        )
        assert len(momentum_calls) == 1
        await db.commit()
