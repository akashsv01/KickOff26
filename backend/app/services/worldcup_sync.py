"""Idempotent sync of rezarahiminia World Cup 2026 reference data into Postgres.

Fetches /get/teams, /get/stadiums, /get/games, /get/groups once and upserts by
api_object_id (_id). Resolves sequential id references (home_team_id, stadium_id)
via api_seq_id on Team/Stadium rows, then links each game to the openfootball-seeded
Match row (same home/away team codes).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ApiCache, Match, Stadium, Team
from app.services.openfootball import OFFICIAL_EXTERNAL_PREFIX
from app.services.tournament_2026 import HOST_CITIES, STADIUM_TO_CITY
from app.services.worldcup_api import WorldCupApiClient
from app.services.worldcup_parse import (
    _first,
    api_object_id,
    api_seq_id,
    map_stage,
    normalize_code,
    parse_int,
    parse_local_date,
)

logger = logging.getLogger(__name__)

GROUPS_KEY = "worldcup:groups"
TEAMS_KEY = "worldcup:teams"
STADIUMS_KEY = "worldcup:stadiums"


def _host_city_meta(city_en: str | None, stadium_name: str | None) -> dict:
    if city_en and city_en in HOST_CITIES:
        return HOST_CITIES[city_en]
    if stadium_name:
        city = STADIUM_TO_CITY.get(stadium_name.lower())
        if city and city in HOST_CITIES:
            return HOST_CITIES[city]
    return {}


async def _cache_put(db: AsyncSession, key: str, payload: Any, *, hours: int = 24) -> None:
    expires = datetime.now(timezone.utc) + timedelta(hours=hours)
    row = (await db.execute(select(ApiCache).where(ApiCache.cache_key == key))).scalar_one_or_none()
    if row:
        row.payload = payload
        row.expires_at = expires
    else:
        db.add(ApiCache(cache_key=key, payload=payload, expires_at=expires))
    await db.flush()


async def upsert_stadiums(db: AsyncSession, raw_stadiums: list[dict]) -> dict[str, Stadium]:
    """Upsert stadiums by api_object_id; index by api_seq_id."""
    by_seq: dict[str, Stadium] = {}
    for item in raw_stadiums:
        if not isinstance(item, dict):
            continue
        oid = api_object_id(item)
        seq = api_seq_id(item)
        if not oid:
            continue

        row = (
            await db.execute(select(Stadium).where(Stadium.api_object_id == oid))
        ).scalar_one_or_none()
        if row is None and seq:
            row = (
                await db.execute(select(Stadium).where(Stadium.api_seq_id == seq))
            ).scalar_one_or_none()

        name_en = str(_first(item, "name_en", "name") or "Stadium")
        city_en = _first(item, "city_en", "city")
        meta = _host_city_meta(str(city_en) if city_en else None, name_en)

        if row is None:
            row = Stadium(api_object_id=oid)
            db.add(row)

        row.api_object_id = oid
        row.api_seq_id = seq
        row.name_en = name_en
        row.name_fa = _first(item, "name_fa")
        row.fifa_name = _first(item, "fifa_name")
        row.city_en = str(city_en) if city_en else None
        row.country_en = _first(item, "country_en", "country")
        row.capacity = parse_int(_first(item, "capacity"))
        row.region = _first(item, "region")
        row.lat = meta.get("lat")
        row.lng = meta.get("lng")
        await db.flush()
        if seq:
            by_seq[seq] = row

    logger.info("WorldCup sync: upserted %s stadiums", len(by_seq))
    return by_seq


async def upsert_teams(db: AsyncSession, raw_teams: list[dict]) -> dict[str, Team]:
    """Upsert API ids onto existing Team rows matched by fifa_code."""
    code_to_team = {t.code: t for t in (await db.execute(select(Team))).scalars().all()}
    by_seq: dict[str, Team] = {}
    normalized: list[dict] = []

    for item in raw_teams:
        if not isinstance(item, dict):
            continue
        oid = api_object_id(item)
        seq = api_seq_id(item)
        code = normalize_code(_first(item, "fifa_code", "fifaCode", "code"))
        if not code or not oid:
            continue

        team = code_to_team.get(code)
        if not team:
            logger.warning("WorldCup sync: no local team for fifa_code %s", code)
            continue

        team.api_object_id = oid
        team.api_seq_id = seq
        team.iso2 = (_first(item, "iso2") or team.iso2 or "")[:4] or None
        flag = _first(item, "flag", "flag_url")
        if flag:
            team.flag_url = str(flag)
        name_en = _first(item, "name_en", "name")
        if name_en:
            team.name = str(name_en)
        group = _first(item, "groups", "group", "group_letter")
        if group:
            team.group_letter = str(group).replace("Group ", "").strip()[:2]

        await db.flush()
        if seq:
            by_seq[seq] = team
        normalized.append(
            {
                "api_object_id": oid,
                "api_seq_id": seq,
                "code": code,
                "name": team.name,
                "flag": team.flag_url,
                "group": team.group_letter,
                "iso2": team.iso2,
            }
        )

    await _cache_put(db, TEAMS_KEY, normalized, hours=24)
    logger.info("WorldCup sync: mapped %s teams (seq ids)", len(by_seq))
    return by_seq


async def _find_schedule_match(
    db: AsyncSession,
    home: Team,
    away: Team,
    *,
    group: str | None,
) -> Match | None:
    q = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(
            Match.home_team_id == home.id,
            Match.away_team_id == away.id,
            Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"),
        )
    )
    if group:
        q = q.where(Match.group_letter == group)
    return (await db.execute(q)).scalar_one_or_none()


async def _find_knockout_slot(db: AsyncSession, official_no: int | None) -> Match | None:
    """Locate a pre-seeded knockout bracket slot by official WC match number.

    For knockout games the API's sequential ``id`` is the official match number
    (e.g. 73), which the openfootball seed encodes as ``wc2026-m073``. The slot
    rows carry placeholder teams (``2A`` vs ``2B``); we keep the slot (and its
    bracket-tree position) and fill in the real qualified teams from the feed.
    """
    if not official_no:
        return None
    ext = f"{OFFICIAL_EXTERNAL_PREFIX}{official_no:03d}"
    return (
        await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(Match.external_id == ext)
        )
    ).scalar_one_or_none()


def _slot_code_from_label(label: str | None) -> str | None:
    """Map an API knockout seeding label to the bracket placeholder code.

    ``"Winner Group E" -> "1E"``, ``"Runner-up Group C" -> "2C"``,
    ``"3rd Group A/B/C/D/F" -> "3ABCDF"``. Returns None if unrecognized.
    Used only as a sanity assertion against the match-number slot mapping.
    """
    if not label:
        return None
    s = label.strip()
    low = s.lower()
    if low.startswith("winner group "):
        return "1" + s.rsplit(" ", 1)[-1].upper()
    if low.startswith("runner-up group ") or low.startswith("runner up group "):
        return "2" + s.rsplit(" ", 1)[-1].upper()
    if low.startswith("3rd group ") or low.startswith("third group "):
        groups = s.split("roup", 1)[-1]
        return "3" + "".join(ch for ch in groups.upper() if ch.isalpha())
    return None


async def upsert_games(
    db: AsyncSession,
    raw_games: list[dict],
    *,
    teams_by_seq: dict[str, Team],
    stadiums_by_seq: dict[str, Stadium],
) -> dict[str, int]:
    stats = {"linked": 0, "updated": 0, "skipped": 0, "unresolved_teams": 0, "knockout": 0}

    for game in raw_games:
        if not isinstance(game, dict):
            stats["skipped"] += 1
            continue

        oid = api_object_id(game)
        seq = api_seq_id(game)
        if not oid:
            stats["skipped"] += 1
            continue

        home_seq = str(_first(game, "home_team_id", "homeTeamId") or "")
        away_seq = str(_first(game, "away_team_id", "awayTeamId") or "")
        home = teams_by_seq.get(home_seq)
        away = teams_by_seq.get(away_seq)
        if not home or not away:
            stats["unresolved_teams"] += 1
            continue

        stadium_seq = str(_first(game, "stadium_id", "stadiumId") or "")
        stadium = stadiums_by_seq.get(stadium_seq)

        match = (
            await db.execute(
                select(Match)
                .options(selectinload(Match.home_team), selectinload(Match.away_team))
                .where(Match.api_object_id == oid)
            )
        ).scalar_one_or_none()

        api_type = _first(game, "type")
        is_knockout = map_stage(api_type) != "group"

        group = _first(game, "group", "group_letter")
        group_letter = str(group).replace("Group ", "").strip()[:2] if group else None

        if match is None:
            if is_knockout:
                # Knockout slots carry placeholder teams (2A vs 2B), so they
                # can't be matched by real team codes - locate the bracket slot
                # by official match number (the API id == official WC match no.)
                # and fill in the real qualified teams below.
                match = await _find_knockout_slot(db, parse_int(seq))
            else:
                match = await _find_schedule_match(db, home, away, group=group_letter)

        if match is None:
            stats["skipped"] += 1
            continue

        if is_knockout:
            # Sanity-check the API seeding labels against the slot's placeholder
            # codes (warn-only; the official match-number mapping is authoritative).
            slot_home = match.home_team.code if match.home_team else None
            slot_away = match.away_team.code if match.away_team else None
            lbl_home = _slot_code_from_label(_first(game, "home_team_label"))
            lbl_away = _slot_code_from_label(_first(game, "away_team_label"))
            if (lbl_home and slot_home and lbl_home != slot_home) or (
                lbl_away and slot_away and lbl_away != slot_away
            ):
                logger.warning(
                    "Knockout slot %s seeding mismatch: slot=%s/%s api_label=%s/%s teams=%s/%s",
                    match.external_id, slot_home, slot_away, lbl_home, lbl_away,
                    home.code, away.code,
                )
            # Resolve the placeholder slot to the real qualified teams.
            match.home_team_id = home.id
            match.away_team_id = away.id
            stats["knockout"] += 1

        was_linked = match.api_object_id is None
        match.api_object_id = oid
        match.api_seq_id = seq
        if seq:
            match.api_fixture_id = parse_int(seq)
        match.stadium_id = stadium.id if stadium else match.stadium_id
        match.matchday = str(_first(game, "matchday") or "") or match.matchday
        match.wc_match_type = api_type or match.wc_match_type
        if group_letter and not is_knockout:
            match.group_letter = group_letter
        match.stage = map_stage(match.wc_match_type)

        if stadium:
            meta = _host_city_meta(stadium.city_en, stadium.name_en)
            match.venue = stadium.name_en or stadium.fifa_name or match.venue
            match.city = stadium.city_en or match.city
            match.country = stadium.country_en or match.country
            if stadium.lat is not None:
                match.stadium_lat = stadium.lat
            if stadium.lng is not None:
                match.stadium_lng = stadium.lng
            elif meta:
                match.stadium_lat = meta.get("lat", match.stadium_lat)
                match.stadium_lng = meta.get("lng", match.stadium_lng)

        kickoff, cal_date = parse_local_date(
            _first(game, "local_date", "localDate"),
            city_en=stadium.city_en if stadium else match.city,
        )
        # Knockout slots are seeded with placeholder kickoff times; the feed is
        # authoritative now that the fixtures are set, so override for knockout.
        if kickoff and (is_knockout or not match.kickoff_at):
            match.kickoff_at = kickoff
        if cal_date:
            match.local_date = cal_date

        await db.flush()
        if was_linked:
            stats["linked"] += 1
        else:
            stats["updated"] += 1

    logger.info(
        "WorldCup sync games: linked=%s updated=%s skipped=%s unresolved_teams=%s knockout=%s",
        stats["linked"],
        stats["updated"],
        stats["skipped"],
        stats["unresolved_teams"],
        stats["knockout"],
    )
    return stats


async def sync_worldcup_data(db: AsyncSession, client: WorldCupApiClient | None = None) -> dict:
    """Full idempotent sync - safe to re-run (upsert by api_object_id)."""
    client = client or WorldCupApiClient()
    if not client.configured:
        return {"ok": False, "error": "WORLDCUP_API_TOKEN not set"}

    raw_teams = await client.get_teams()
    raw_stadiums = await client.get_stadiums()
    raw_games = await client.get_games()
    raw_groups = await client.get_groups()

    stadiums_by_seq = await upsert_stadiums(db, raw_stadiums)
    teams_by_seq = await upsert_teams(db, raw_teams)
    game_stats = await upsert_games(
        db,
        raw_games,
        teams_by_seq=teams_by_seq,
        stadiums_by_seq=stadiums_by_seq,
    )

    if raw_stadiums:
        await _cache_put(db, STADIUMS_KEY, raw_stadiums, hours=24 * 7)
    if raw_groups:
        await _cache_put(db, GROUPS_KEY, raw_groups, hours=6)

    mapped_games = (
        await db.execute(
            select(Match).where(Match.api_object_id.isnot(None))
        )
    ).scalars().all()

    return {
        "ok": True,
        "teams": len(teams_by_seq),
        "stadiums": len(stadiums_by_seq),
        "games_api": len(raw_games),
        "games_mapped": len(mapped_games),
        **game_stats,
    }


# ---- Legacy helpers used by poller (load maps from DB, not cache) -----------------

async def load_teams_by_seq(db: AsyncSession) -> dict[str, Team]:
    rows = (await db.execute(select(Team).where(Team.api_seq_id.isnot(None)))).scalars().all()
    return {t.api_seq_id: t for t in rows if t.api_seq_id}


async def load_team_id_map(db: AsyncSession) -> dict[str, str]:
    """Sequential api id -> team code (for live apply fallback)."""
    rows = (await db.execute(select(Team).where(Team.api_seq_id.isnot(None)))).scalars().all()
    return {t.api_seq_id: t.code for t in rows if t.api_seq_id}


async def load_stadiums_by_seq(db: AsyncSession) -> dict[str, Stadium]:
    rows = (await db.execute(select(Stadium).where(Stadium.api_seq_id.isnot(None)))).scalars().all()
    return {s.api_seq_id: s for s in rows if s.api_seq_id}


async def sync_groups_snapshot(db: AsyncSession, client: WorldCupApiClient) -> int:
    groups = await client.get_groups()
    if groups:
        await _cache_put(db, GROUPS_KEY, groups, hours=6)
    return len(groups)


# Backward-compatible alias
async def bootstrap_worldcup_mode(db: AsyncSession) -> dict:
    return await sync_worldcup_data(db)
