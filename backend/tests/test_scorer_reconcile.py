"""Live monotonic scorer acceptance + honest finish reconciliation.

parse_scorers_clean is count-tolerant (live); parse_scorers is the strict
count-matching verifier (reconciler only). Finished matches store the best clean
scorer set under the correct final score, and reconciled is True only when both
sides are clean AND count-match - otherwise reconcile_attempted=True, score intact.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db import async_session
from app.models import Match, MatchEvent, MatchStatus
from app.services.worldcup_live import (
    apply_game_snapshot,
    build_code_map,
    build_game_object_id_map,
)
from app.services.worldcup_parse import parse_scorers, parse_scorers_clean
from app.services.worldcup_sync import upsert_games, upsert_stadiums, upsert_teams
from tests.test_worldcup_mapping import (
    SAMPLE_GAME,
    SAMPLE_STADIUM,
    SAMPLE_TEAM_AUS,
    SAMPLE_TEAM_TUR,
)


# --------------------------------------------------------------------------- #
# Unit: lenient (live) vs strict (reconciler) parsing
# --------------------------------------------------------------------------- #

def test_parse_scorers_clean_is_count_tolerant():
    assert parse_scorers_clean("{\"A. One 10'\",\"B. Two 20'\"}") == [
        {"player_name": "A. One", "minute": 10, "added_time": None, "raw": "A. One 10'"},
        {"player_name": "B. Two", "minute": 20, "added_time": None, "raw": "B. Two 20'"},
    ]


def test_parse_scorers_clean_null_is_empty_not_none():
    assert parse_scorers_clean("null") == []
    assert parse_scorers_clean("{}") == []


def test_parse_scorers_clean_non_latin_holds():
    # Persian transliteration -> untrusted -> None (caller HOLDs last good set).
    assert parse_scorers_clean("{\"فلورین 7'\"}") is None


def test_parse_scorers_clean_stoppage_time():
    assert parse_scorers_clean("{\"K. Lee 90'+6'\"}") == [
        {"player_name": "K. Lee", "minute": 90, "added_time": 6, "raw": "K. Lee 90'+6'"}
    ]


def test_parse_scorers_strict_count_gate():
    assert parse_scorers("{\"A. One 10'\"}", 1) is not None  # clean + count matches
    assert parse_scorers("{\"A. One 10'\"}", 3) is None      # count mismatch -> None
    assert parse_scorers("null", 0) == []                    # genuine 0-goal side


# --------------------------------------------------------------------------- #
# Integration: finish reconciliation + live monotonic acceptance
# --------------------------------------------------------------------------- #

async def _reset_sample_match(db) -> int:
    teams_by_seq = await upsert_teams(db, [SAMPLE_TEAM_AUS, SAMPLE_TEAM_TUR])
    stadiums_by_seq = await upsert_stadiums(db, [SAMPLE_STADIUM])
    await upsert_games(db, [SAMPLE_GAME], teams_by_seq=teams_by_seq, stadiums_by_seq=stadiums_by_seq)
    match = (
        await db.execute(select(Match).where(Match.api_object_id == SAMPLE_GAME["_id"]))
    ).scalar_one()
    match.status = MatchStatus.SCHEDULED
    match.home_score = None
    match.away_score = None
    match.scorers_reconciled = False
    match.reconcile_attempted = False
    await db.execute(MatchEvent.__table__.delete().where(MatchEvent.match_id == match.id))
    await db.commit()
    return match.id


async def _apply(db, game) -> None:
    code_map = await build_code_map(db)
    oid_map = await build_game_object_id_map(db)
    teams_by_seq = await upsert_teams(db, [SAMPLE_TEAM_AUS, SAMPLE_TEAM_TUR])
    await apply_game_snapshot(
        db, game, code_map=code_map, oid_map=oid_map, teams_by_seq=teams_by_seq, emit_alerts=False
    )
    await db.commit()


async def _goals(db, match_id: int, side: str) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(MatchEvent)
            .where(
                MatchEvent.match_id == match_id,
                MatchEvent.event_type == "goal",
                MatchEvent.team_side == side,
            )
        )
    ).scalar_one()


def _finished(home_score, away_score, home_scorers, away_scorers) -> dict:
    return {
        **SAMPLE_GAME,
        "finished": "TRUE",
        "time_elapsed": "finished",
        "home_score": str(home_score),
        "away_score": str(away_score),
        "home_scorers": home_scorers,
        "away_scorers": away_scorers,
    }


def _live(home_score, away_score, home_scorers, away_scorers) -> dict:
    return {
        **SAMPLE_GAME,
        "finished": "FALSE",
        "time_elapsed": "55",
        "home_score": str(home_score),
        "away_score": str(away_score),
        "home_scorers": home_scorers,
        "away_scorers": away_scorers,
    }


@pytest.mark.asyncio
async def test_finish_incomplete_home_scorers_best_effort(setup_db):
    """SWE-TUN: 2 clean home scorers but score 5 -> store 2, score 5-1, NOT reconciled."""
    async with async_session() as db:
        mid = await _reset_sample_match(db)
    async with async_session() as db:
        await _apply(db, _finished(5, 1, "{\"A. One 10'\",\"B. Two 20'\"}", "{\"C. Three 30'\"}"))
        m = (await db.execute(select(Match).where(Match.id == mid))).scalar_one()
        assert m.status == MatchStatus.FINISHED
        assert (m.home_score, m.away_score) == (5, 1)        # score intact
        assert await _goals(db, mid, "home") == 2            # best clean effort, not garbage
        assert await _goals(db, mid, "away") == 1
        assert m.reconcile_attempted is True
        assert m.scorers_reconciled is False                 # home 2 != 5


@pytest.mark.asyncio
async def test_finish_zero_usable_scorers(setup_db):
    """CIV-ECU: 0 usable scorers for a 1-0 -> store 0, score 1-0, NOT reconciled."""
    async with async_session() as db:
        mid = await _reset_sample_match(db)
    async with async_session() as db:
        await _apply(db, _finished(1, 0, "null", "null"))
        m = (await db.execute(select(Match).where(Match.id == mid))).scalar_one()
        assert (m.home_score, m.away_score) == (1, 0)
        assert await _goals(db, mid, "home") == 0
        assert await _goals(db, mid, "away") == 0
        assert m.reconcile_attempted is True
        assert m.scorers_reconciled is False


@pytest.mark.asyncio
async def test_finish_clean_count_match_reconciles(setup_db):
    """GER 7-1: 7 clean home + 1 clean away matching the score -> reconciled True."""
    home = "{" + ",".join(f"\"{n} {m}'\"" for n, m in
                          [("Ann", 5), ("Bob", 10), ("Cy", 15), ("Dee", 20),
                           ("Ed", 25), ("Fin", 30), ("Gus", 35)]) + "}"
    async with async_session() as db:
        mid = await _reset_sample_match(db)
    async with async_session() as db:
        await _apply(db, _finished(7, 1, home, "{\"Hal 40'\"}"))
        m = (await db.execute(select(Match).where(Match.id == mid))).scalar_one()
        assert (m.home_score, m.away_score) == (7, 1)
        assert await _goals(db, mid, "home") == 7
        assert await _goals(db, mid, "away") == 1
        assert m.reconcile_attempted is True
        assert m.scorers_reconciled is True


@pytest.mark.asyncio
async def test_live_monotonic_holds_then_grows(setup_db):
    """A transient empty/lagging payload never wipes a larger good set; score is independent."""
    async with async_session() as db:
        mid = await _reset_sample_match(db)
    async with async_session() as db:
        # 1) live 2-0 with 2 clean home scorers -> stored 2
        await _apply(db, _live(2, 0, "{\"Ann 10'\",\"Bob 20'\"}", "null"))
        assert await _goals(db, mid, "home") == 2
        # 2) score grows to 3 but scorers lag (empty) -> HOLD at 2, score updates to 3
        await _apply(db, _live(3, 0, "null", "null"))
        m = (await db.execute(select(Match).where(Match.id == mid))).scalar_one()
        assert m.home_score == 3
        assert await _goals(db, mid, "home") == 2  # not wiped
        # 3) clean 3-scorer payload arrives -> grow to 3
        await _apply(db, _live(3, 0, "{\"Ann 10'\",\"Bob 20'\",\"Cy 30'\"}", "null"))
        assert await _goals(db, mid, "home") == 3


@pytest.mark.asyncio
async def test_duplicate_scorer_rows_are_collapsed(setup_db):
    """A duplicate goal row (a NULL added_time slips past the unique constraint)
    is collapsed on the next clean apply, not held forever."""
    async with async_session() as db:
        mid = await _reset_sample_match(db)
        for _ in range(2):  # two identical away rows, as a legacy duplicate would be
            db.add(
                MatchEvent(
                    match_id=mid,
                    event_type="goal",
                    team_side="away",
                    player_name="O. Rekik",
                    minute=43,
                    added_time=None,
                    detail="",
                )
            )
        await db.commit()
        assert await _goals(db, mid, "away") == 2

    async with async_session() as db:
        # Live snapshot with one clean Rekik goal -> duplicate collapses to one row.
        await _apply(db, _live(0, 1, "null", "{\"O. Rekik 43'\"}"))
        assert await _goals(db, mid, "away") == 1
