"""Tests for rezarahiminia API dual-ID mapping, parsing, and sync resolution."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Match, MatchStatus, Stadium, Team
from app.services.worldcup_parse import (
    api_object_id,
    api_seq_id,
    derive_status,
    is_english_name,
    parse_finished,
    parse_int,
    parse_local_date,
    parse_scorers,
    split_name_minute,
)
from app.services.worldcup_sync import upsert_games, upsert_stadiums, upsert_teams

SAMPLE_TEAM_AUS = {
    "_id": "679c9c6b5749c4077500ea15",
    "id": "15",
    "name_en": "Australia",
    "fifa_code": "AUS",
    "iso2": "AU",
    "groups": "D",
}

SAMPLE_TEAM_TUR = {
    "_id": "679c9c6b5749c4077500ea16",
    "id": "16",
    "name_en": "Turkey",
    "fifa_code": "TUR",
    "iso2": "TR",
    "groups": "D",
}

SAMPLE_STADIUM = {
    "_id": "679c9c8a5749c4077500f00d",
    "id": "13",
    "name_en": "BC Place",
    "city_en": "Vancouver",
    "country_en": "Canada",
    "capacity": 54500,
    "region": "West",
}

SAMPLE_GAME = {
    "_id": "679c9c8a5749c4077500e006",
    "id": "6",
    "home_team_id": "15",
    "away_team_id": "16",
    "home_score": "0",
    "away_score": "0",
    "home_scorers": "null",
    "away_scorers": "null",
    "group": "D",
    "matchday": "1",
    "local_date": "06/13/2026 21:00",
    "stadium_id": "13",
    "finished": "FALSE",
    "time_elapsed": "notstarted",
    "type": "group",
    "home_team_name_en": "Australia",
    "away_team_name_en": "Turkey",
}


class TestWorldcupParse:
    def test_dual_ids(self):
        assert api_object_id(SAMPLE_GAME) == "679c9c8a5749c4077500e006"
        assert api_seq_id(SAMPLE_GAME) == "6"

    def test_finished_string_not_truthy_bug(self):
        assert parse_finished("FALSE") is False
        assert parse_finished("TRUE") is True

    def test_derive_status_from_time_elapsed_strings(self):
        assert derive_status({**SAMPLE_GAME}) == MatchStatus.SCHEDULED
        assert derive_status({"finished": "FALSE", "time_elapsed": "live"}) == MatchStatus.LIVE
        assert derive_status({"finished": "FALSE", "time_elapsed": "finished"}) == MatchStatus.FINISHED
        assert derive_status({"finished": "TRUE", "time_elapsed": "notstarted"}) == MatchStatus.FINISHED
        assert derive_status({"finished": "FALSE", "time_elapsed": "67"}) == MatchStatus.LIVE

    def test_parse_int_from_strings(self):
        assert parse_int("0") == 0
        assert parse_int("null") is None

    def test_scorers_zero_goals_markers(self):
        # "null"/empty/braces with score 0 -> trustworthy zero goals (never phantom).
        assert parse_scorers("null", 0) == []
        assert parse_scorers("{}", 0) == []
        assert parse_scorers("{ }", 0) == []
        assert parse_scorers("", 0) == []

    def test_real_usa_paraguay_payload(self):
        """The exact observed live payload parses cleanly, incl. 45'+5' stoppage."""
        raw = "{\"D. Bobadilla 7'\",\"F. Balogun 31'\",\"F. Balogun 45'+5'\"}"
        result = parse_scorers(raw, 3)
        assert result == [
            {"player_name": "D. Bobadilla", "minute": 7, "added_time": None, "raw": "D. Bobadilla 7'"},
            {"player_name": "F. Balogun", "minute": 31, "added_time": None, "raw": "F. Balogun 31'"},
            {"player_name": "F. Balogun", "minute": 45, "added_time": 5, "raw": "F. Balogun 45'+5'"},
        ]

    def test_split_name_minute_stoppage(self):
        assert split_name_minute("F. Balogun 45'+5'") == ("F. Balogun", 45, 5)
        assert split_name_minute("Player 90'+2'") == ("Player", 90, 2)
        assert split_name_minute("I.B. Hwang 67'") == ("I.B. Hwang", 67, None)

    def test_own_goal_and_penalty_annotations(self):
        # Trailing (OG)/(pen) annotations are kept and the minute still parses.
        assert split_name_minute("D. Bobadilla 7'(OG)") == ("D. Bobadilla (OG)", 7, None)
        assert split_name_minute("G. Reyna 90'+8'") == ("G. Reyna", 90, 8)
        assert split_name_minute("L. Messi 80'(pen)") == ("L. Messi (pen)", 80, None)

    def test_live_payload_with_og_and_stoppage(self):
        """The evolved live USA-PAR payload (own goal + 90+8 stoppage) parses clean."""
        raw = "{\"D. Bobadilla 7'(OG)\",\"F. Balogun 31'\",\"F. Balogun 45'+5'\",\"G. Reyna 90'+8'\"}"
        result = parse_scorers(raw, 4)
        assert result == [
            {"player_name": "D. Bobadilla (OG)", "minute": 7, "added_time": None, "raw": "D. Bobadilla 7'(OG)"},
            {"player_name": "F. Balogun", "minute": 31, "added_time": None, "raw": "F. Balogun 31'"},
            {"player_name": "F. Balogun", "minute": 45, "added_time": 5, "raw": "F. Balogun 45'+5'"},
            {"player_name": "G. Reyna", "minute": 90, "added_time": 8, "raw": "G. Reyna 90'+8'"},
        ]

    def test_count_mismatch_returns_none(self):
        # Score says 3 but only one scorer parsed -> not trustworthy yet.
        assert parse_scorers("{\"A. Smith 10'\"}", 3) is None
        # Score 1 but feed gives "null" -> not trustworthy (goal exists, no detail).
        assert parse_scorers("null", 1) is None

    def test_phantom_empty_entry_is_not_a_goal(self):
        # Whitespace-only braces: zero goals when score 0, untrusted when score>0.
        assert parse_scorers("{ }", 0) == []
        assert parse_scorers("{ }", 1) is None

    def test_non_english_rejected(self):
        # Persian transliteration -> untrusted; caller keeps last known-good list.
        assert parse_scorers("{“فلورین 7'”}", 1) is None
        assert is_english_name("F. Balogun") is True
        assert is_english_name("J. Quiñones") is True  # Latin diacritics allowed
        assert is_english_name("فلورین") is False

    def test_smart_quotes_and_diacritics(self):
        raw = "{“J. Quiñones 9'”,“R. Jiménez 67'”}"
        result = parse_scorers(raw, 2)
        assert result is not None
        assert [r["player_name"] for r in result] == ["J. Quiñones", "R. Jiménez"]
        assert [r["minute"] for r in result] == [9, 67]

    def test_dict_format_scorers(self):
        # API-Football style array-of-dicts is also accepted.
        result = parse_scorers('[{"scorer":"Smith","minute":"23"}]', 1)
        assert result == [
            {"player_name": "Smith", "minute": 23, "added_time": None, "raw": "Smith"}
        ]

    def test_local_date_parsing(self):
        kickoff, cal = parse_local_date("06/13/2026 21:00", city_en="Vancouver")
        assert kickoff is not None
        assert cal is not None
        assert len(cal) == 10


@pytest.mark.asyncio
async def test_sync_resolves_team_stadium_and_game_ids(setup_db):
    from app.db import async_session

    async with async_session() as db:
        teams_by_seq = await upsert_teams(db, [SAMPLE_TEAM_AUS, SAMPLE_TEAM_TUR])
        stadiums_by_seq = await upsert_stadiums(db, [SAMPLE_STADIUM])

        assert teams_by_seq["15"].code == "AUS"
        assert teams_by_seq["15"].api_object_id == SAMPLE_TEAM_AUS["_id"]
        assert teams_by_seq["15"].api_seq_id == "15"
        assert stadiums_by_seq["13"].city_en == "Vancouver"

        aus = (await db.execute(select(Team).where(Team.code == "AUS"))).scalar_one()
        tur = (await db.execute(select(Team).where(Team.code == "TUR"))).scalar_one()
        match = (
            await db.execute(
                select(Match).where(Match.home_team_id == aus.id, Match.away_team_id == tur.id).limit(1)
            )
        ).scalar_one_or_none()
        assert match is not None

        stats = await upsert_games(
            db,
            [SAMPLE_GAME],
            teams_by_seq=teams_by_seq,
            stadiums_by_seq=stadiums_by_seq,
        )
        await db.commit()
        assert stats["linked"] + stats["updated"] >= 1

        linked = (
            await db.execute(
                select(Match)
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.stadium),
                )
                .where(Match.api_object_id == SAMPLE_GAME["_id"])
            )
        ).scalar_one()

        assert linked.api_seq_id == "6"
        assert linked.home_team.code == "AUS"
        assert linked.away_team.code == "TUR"
        assert linked.stadium is not None
        assert linked.stadium.api_seq_id == "13"


@pytest.mark.asyncio
async def test_live_poller_uses_batch_get_games(setup_db, monkeypatch):
    from app.db import async_session
    from app.services import worldcup_poller

    batch_called = False

    class FakeClient:
        configured = True

        async def get_game(self, game_id):
            raise AssertionError(f"Per-game poll should not be used: {game_id}")

        async def get_games(self):
            nonlocal batch_called
            batch_called = True
            return [{**SAMPLE_GAME, "time_elapsed": "live", "home_score": "1", "away_score": "0"}]

        async def get_groups(self):
            return []

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
        match.status = MatchStatus.LIVE
        await db.commit()

    async def fake_window(_db):
        return type("W", (), {"active": True, "in_live_window": True, "seconds_until_active": 0})()

    monkeypatch.setattr(worldcup_poller, "WorldCupApiClient", FakeClient)
    monkeypatch.setattr(worldcup_poller, "compute_polling_window", fake_window)

    async with async_session() as db:
        await worldcup_poller.poll_once(db)
        match = (
            await db.execute(select(Match).where(Match.api_object_id == SAMPLE_GAME["_id"]))
        ).scalar_one()
        assert match.home_score == 1

    assert batch_called is True
