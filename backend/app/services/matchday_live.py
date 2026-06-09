"""Apply API-Football live snapshots to Postgres and fan out WebSocket updates."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Match, MatchStatus, Team
from app.services.data_sync import _map_status
from app.services.matchday import enrich_match_probs, match_to_dict
from app.services.matchday_alerts import (
    emit_event_alerts,
    emit_prob_momentum,
    emit_status_alert,
    parse_api_events,
)
from app.services.match_events import fetch_events_for_match, insert_new_events
from app.services.openfootball import NAME_TO_CODE, OFFICIAL_EXTERNAL_PREFIX
from app.websocket.gateway import ws_manager

logger = logging.getLogger(__name__)

LIVE_SHORT = frozenset({"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"})
_last_api_short: dict[int, str] = {}


def api_team_code(team: dict) -> str | None:
    name = (team or {}).get("name") or ""
    if name in NAME_TO_CODE:
        return NAME_TO_CODE[name]
    tla = (team or {}).get("code") or (team or {}).get("tla") or ""
    if tla and len(tla) <= 4:
        return tla.upper()
    if name:
        return name[:3].upper()
    return None


async def _broadcast_match_update(db: AsyncSession, match: Match, pre_probs: dict) -> None:
    events = await fetch_events_for_match(db, match.id)
    payload = {"type": "match_update", "match": match_to_dict(match, pre_probs, events=events)}
    await ws_manager.broadcast(ws_manager.match_channel(match.id), payload)
    await ws_manager.broadcast("matches:live", payload)


async def apply_fixture_snapshot(
    db: AsyncSession,
    fx: dict,
    *,
    code_map: dict[str, Team],
    id_map: dict[int, Match],
) -> tuple[Match | None, bool]:
    """Merge one API-Football fixture into DB. Returns (match, needs_event_fetch)."""
    fixture = fx.get("fixture") or {}
    teams = fx.get("teams") or {}
    goals = fx.get("goals") or {}
    fixture_id = fixture.get("id")
    if not fixture_id:
        return None, False

    home_api = teams.get("home") or {}
    away_api = teams.get("away") or {}
    home_code = api_team_code(home_api)
    away_code = api_team_code(away_api)
    if not home_code or not away_code:
        return None, False

    match = id_map.get(fixture_id)
    if not match:
        home_team = code_map.get(home_code)
        away_team = code_map.get(away_code)
        if not home_team or not away_team:
            return None, False
        result = await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(
                Match.home_team_id == home_team.id,
                Match.away_team_id == away_team.id,
                Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"),
            )
        )
        match = result.scalar_one_or_none()
        if match:
            match.api_fixture_id = fixture_id
            id_map[fixture_id] = match

    if not match:
        return None, False

    old_status = match.status
    old_short = _last_api_short.get(match.id)
    old_probs = {
        "home": match.win_prob_home or 0.33,
        "draw": match.win_prob_draw or 0.33,
        "away": match.win_prob_away or 0.33,
    }
    old_home = match.home_score
    old_away = match.away_score

    short = (fixture.get("status") or {}).get("short") or "NS"
    elapsed = (fixture.get("status") or {}).get("elapsed")
    match.minute = elapsed
    if goals.get("home") is not None:
        match.home_score = goals.get("home")
        match.away_score = goals.get("away")

    if short in LIVE_SHORT:
        if old_status == MatchStatus.SCHEDULED:
            match.status = MatchStatus.LIVE
            await emit_status_alert(
                match,
                "match_start_alert",
                f"KICK OFF: {match.home_team.code} vs {match.away_team.code}",
            )
        else:
            match.status = MatchStatus.LIVE
        if short == "HT" and old_short != "HT":
            await emit_status_alert(
                match,
                "match_halftime_alert",
                f"HALF TIME: {match.home_team.code} {match.home_score or 0}-"
                f"{match.away_score or 0} {match.away_team.code}",
            )
    elif short in ("FT", "AET", "PEN", "AWD", "WO"):
        if match.status != MatchStatus.FINISHED:
            match.status = MatchStatus.FINISHED
            await emit_status_alert(
                match,
                "match_end_alert",
                f"FULL TIME: {match.home_team.code} {match.home_score}-"
                f"{match.away_score} {match.away_team.code}",
            )
    else:
        match.status = _map_status(short)

    _last_api_short[match.id] = short

    score_changed = (
        match.home_score != old_home
        or match.away_score != old_away
        or (old_status != MatchStatus.LIVE and match.status == MatchStatus.LIVE)
    )

    enriched = await enrich_match_probs(match, events=await fetch_events_for_match(db, match.id))
    new_probs = enriched["probs"]
    await emit_prob_momentum(match, old_probs, new_probs)
    await _broadcast_match_update(db, match, enriched["pre_probs"])

    needs_events = score_changed and match.status == MatchStatus.LIVE
    return match, needs_events


async def merge_api_events(
    db: AsyncSession,
    match: Match,
    raw_events: list[dict],
    api_home_id: int,
) -> bool:
    """Ingest events into match_events; alert only on newly inserted rows."""
    parsed = parse_api_events(raw_events, api_home_id)
    inserted = await insert_new_events(db, match.id, parsed)
    if not inserted:
        return False
    return await emit_event_alerts(match, inserted)


async def build_match_maps(db: AsyncSession) -> tuple[dict[str, Team], dict[int, Match]]:
    teams = (await db.execute(select(Team))).scalars().all()
    code_map = {t.code: t for t in teams}
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.api_fixture_id.isnot(None))
    )
    id_map = {m.api_fixture_id: m for m in result.scalars().all() if m.api_fixture_id}
    return code_map, id_map


async def link_api_fixture_ids(db: AsyncSession, client) -> int:
    """One daily call: map API fixture IDs onto openfootball schedule rows."""
    from app.services.api_football import ApiFootballClient

    if not isinstance(client, ApiFootballClient):
        client = ApiFootballClient(db)

    fixtures = await client.fetch_season_fixtures()
    if not fixtures:
        return 0

    code_map = {t.code: t for t in (await db.execute(select(Team))).scalars().all()}
    linked = 0
    for fx in fixtures:
        fixture = fx.get("fixture") or {}
        fid = fixture.get("id")
        teams = fx.get("teams") or {}
        hc = api_team_code(teams.get("home") or {})
        ac = api_team_code(teams.get("away") or {})
        if not fid or not hc or not ac or hc not in code_map or ac not in code_map:
            continue
        result = await db.execute(
            select(Match).where(
                Match.home_team_id == code_map[hc].id,
                Match.away_team_id == code_map[ac].id,
                Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"),
            )
        )
        match = result.scalar_one_or_none()
        if match and match.api_fixture_id != fid:
            match.api_fixture_id = fid
            linked += 1
    await db.flush()
    logger.info("Linked %s API-Football fixture IDs to schedule rows", linked)
    return linked
