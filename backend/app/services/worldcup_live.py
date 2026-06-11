"""Apply rezarahiminia World Cup 2026 game snapshots to Postgres + WebSocket fanout.

Matches are resolved primarily by api_object_id (_id). Live polling uses
GET /get/game/{api_object_id}. Sequential ids (home_team_id, stadium_id) are
resolved via Team.api_seq_id / Stadium.api_seq_id set during sync.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Match, MatchStatus, Team
from app.services.matchday import enrich_match_probs, match_to_dict
from app.services.matchday_alerts import (
    UNKNOWN_PLAYER,
    build_event_alert,
    broadcast_alert,
    emit_prob_momentum,
    emit_status_alert,
)
from app.services.match_events import fetch_events_for_match, insert_new_events
from app.services.openfootball import OFFICIAL_EXTERNAL_PREFIX
from app.services.worldcup_parse import (
    _first,
    api_object_id,
    derive_status,
    normalize_code,
    parse_elapsed_minute,
    parse_int,
    parse_scorer_events,
)
from app.websocket.gateway import ws_manager

logger = logging.getLogger(__name__)


def game_team_codes_from_db(game: dict, teams_by_seq: dict[str, Team]) -> tuple[str | None, str | None]:
    home_seq = str(_first(game, "home_team_id", "homeTeamId") or "")
    away_seq = str(_first(game, "away_team_id", "awayTeamId") or "")
    home = teams_by_seq.get(home_seq)
    away = teams_by_seq.get(away_seq)
    if home and away:
        return home.code, away.code
    home_code = normalize_code(_first(game, "home_team_name_en", "home_team_name"))
    away_code = normalize_code(_first(game, "away_team_name_en", "away_team_name"))
    return home_code, away_code


async def build_code_map(db: AsyncSession) -> dict[str, Team]:
    teams = (await db.execute(select(Team))).scalars().all()
    return {t.code: t for t in teams}


async def build_game_object_id_map(db: AsyncSession) -> dict[str, Match]:
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.api_object_id.isnot(None))
    )
    return {m.api_object_id: m for m in result.scalars().all() if m.api_object_id}


async def _resolve_match(
    db: AsyncSession,
    game: dict,
    *,
    code_map: dict[str, Team],
    oid_map: dict[str, Match],
    teams_by_seq: dict[str, Team],
) -> Match | None:
    oid = api_object_id(game)
    if oid and oid in oid_map:
        return oid_map[oid]

    if oid:
        row = (
            await db.execute(
                select(Match)
                .options(selectinload(Match.home_team), selectinload(Match.away_team))
                .where(Match.api_object_id == oid)
            )
        ).scalar_one_or_none()
        if row:
            oid_map[oid] = row
            return row

    home_code, away_code = game_team_codes_from_db(game, teams_by_seq)
    if not home_code or not away_code:
        return None
    home = code_map.get(home_code)
    away = code_map.get(away_code)
    if not home or not away:
        return None

    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(
            Match.home_team_id == home.id,
            Match.away_team_id == away.id,
            Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"),
        )
    )
    match = result.scalar_one_or_none()
    if match and oid:
        match.api_object_id = oid
        seq = _first(game, "id", "game_id")
        if seq:
            match.api_seq_id = str(seq)
            match.api_fixture_id = parse_int(seq)
        oid_map[oid] = match
    return match


async def _broadcast_match_update(db: AsyncSession, match: Match, pre_probs: dict) -> None:
    events = await fetch_events_for_match(db, match.id)
    payload = {"type": "match_update", "match": match_to_dict(match, pre_probs, events=events)}
    await ws_manager.broadcast(ws_manager.match_channel(match.id), payload)
    await ws_manager.broadcast("matches:live", payload)


def _goal_alerts_from_score_delta(
    match: Match,
    *,
    old_home: int | None,
    old_away: int | None,
    inserted_goals: list[dict],
) -> list[dict]:
    """Emit goal alerts for score increases not already covered by new scorer rows."""
    new_home = match.home_score or 0
    new_away = match.away_score or 0
    home_delta = max(0, new_home - (old_home or 0))
    away_delta = max(0, new_away - (old_away or 0))
    home_from_scorers = sum(
        1 for ev in inserted_goals if ev.get("type") == "goal" and ev.get("team") == "home"
    )
    away_from_scorers = sum(
        1 for ev in inserted_goals if ev.get("type") == "goal" and ev.get("team") == "away"
    )
    alerts: list[dict] = []
    minute = match.minute or 0
    for _ in range(home_delta - home_from_scorers):
        alerts.append(
            {"type": "goal", "minute": minute, "team": "home", "player": UNKNOWN_PLAYER}
        )
    for _ in range(away_delta - away_from_scorers):
        alerts.append(
            {"type": "goal", "minute": minute, "team": "away", "player": UNKNOWN_PLAYER}
        )
    return alerts


async def apply_game_snapshot(
    db: AsyncSession,
    game: dict,
    *,
    code_map: dict[str, Team],
    oid_map: dict[str, Match],
    teams_by_seq: dict[str, Team],
    emit_alerts: bool = True,
) -> Match | None:
    match = await _resolve_match(
        db, game, code_map=code_map, oid_map=oid_map, teams_by_seq=teams_by_seq
    )
    if not match:
        return None

    old_status = match.status
    old_home = match.home_score
    old_away = match.away_score
    old_minute = match.minute
    old_probs = {
        "home": match.win_prob_home or 0.33,
        "draw": match.win_prob_draw or 0.33,
        "away": match.win_prob_away or 0.33,
    }

    new_status = derive_status(game)
    home_score = parse_int(_first(game, "home_score", "homeScore", "score_home"))
    away_score = parse_int(_first(game, "away_score", "awayScore", "score_away"))
    elapsed = parse_elapsed_minute(_first(game, "time_elapsed", "timeElapsed", "elapsed"))

    if new_status == MatchStatus.SCHEDULED:
        match.home_score = None
        match.away_score = None
        match.minute = None
    elif new_status == MatchStatus.LIVE:
        match.home_score = home_score if home_score is not None else 0
        match.away_score = away_score if away_score is not None else 0
        match.minute = elapsed
    else:
        if home_score is not None:
            match.home_score = home_score
        if away_score is not None:
            match.away_score = away_score
        match.minute = elapsed if elapsed is not None else match.minute
    match.status = new_status

    score_changed = (old_home or 0) != (match.home_score or 0) or (old_away or 0) != (
        match.away_score or 0
    )

    if emit_alerts:
        if old_status != MatchStatus.LIVE and new_status == MatchStatus.LIVE:
            await emit_status_alert(
                match,
                "match_start_alert",
                f"KICK OFF: {match.home_team.code} vs {match.away_team.code}",
            )
        elif old_status != MatchStatus.FINISHED and new_status == MatchStatus.FINISHED:
            await emit_status_alert(
                match,
                "match_end_alert",
                f"FULL TIME: {match.home_team.code} {match.home_score or 0}-"
                f"{match.away_score or 0} {match.away_team.code}",
            )

    parsed_goals = parse_scorer_events(game)
    inserted = await insert_new_events(db, match.id, parsed_goals) if parsed_goals else []

    if emit_alerts:
        for ev in inserted:
            if ev.get("type") == "goal":
                await broadcast_alert(build_event_alert(match, ev), match.id)
        for ev in _goal_alerts_from_score_delta(
            match, old_home=old_home, old_away=old_away, inserted_goals=inserted
        ):
            await broadcast_alert(build_event_alert(match, ev), match.id)

    enriched = await enrich_match_probs(match, events=await fetch_events_for_match(db, match.id))
    if emit_alerts and score_changed:
        await emit_prob_momentum(match, old_probs, enriched["probs"])

    changed = (
        old_status != match.status
        or (old_home or 0) != (match.home_score or 0)
        or (old_away or 0) != (match.away_score or 0)
        or old_minute != match.minute
        or bool(inserted)
    )
    if changed:
        await _broadcast_match_update(db, match, enriched["pre_probs"])
    return match


async def reconcile_all_games_from_api(
    db: AsyncSession,
    games: list[dict],
    *,
    emit_alerts: bool = False,
) -> int:
    """Apply API snapshots to every mapped game (baseline sync, no alert spam)."""
    code_map = await build_code_map(db)
    oid_map = await build_game_object_id_map(db)
    teams_by_seq = {
        t.api_seq_id: t
        for t in (await db.execute(select(Team).where(Team.api_seq_id.isnot(None)))).scalars()
        if t.api_seq_id
    }
    applied = 0
    for game in games:
        if isinstance(game, dict) and await apply_game_snapshot(
            db,
            game,
            code_map=code_map,
            oid_map=oid_map,
            teams_by_seq=teams_by_seq,
            emit_alerts=emit_alerts,
        ):
            applied += 1
    return applied
