"""MatchDay companion: live scores, win probabilities, following feed, alerts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Match, MatchStatus, Team
from app.models.win_probability import engine
from app.services.match_calendar import match_calendar_date, summarize_match_days
from app.services.match_events import (
    fetch_events_by_match_ids,
    fetch_events_for_match,
    insert_new_events,
    migrate_json_events_if_needed,
)
from app.services.openfootball import OFFICIAL_EXTERNAL_PREFIX
from app.services.match_lineups import ensure_demo_lineups, get_lineup_row, lineup_to_detail_fields

PROB_SHIFT_THRESHOLD = 0.15

_DEMO_SEED_EVENTS = [
    {"type": "goal", "minute": 12, "team": "home", "player": "Jiménez"},
    {"type": "goal", "minute": 34, "team": "away", "player": "Promes"},
    {"type": "goal", "minute": 51, "team": "home", "player": "Lozano"},
    {"type": "yellow_card", "minute": 45, "team": "away", "player": "Mokoena"},
]


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _model_context(home_code: str, away_code: str, probs: dict[str, float], pre_probs: dict[str, float] | None = None) -> dict:
    home_elo = round(engine.get_elo(home_code))
    away_elo = round(engine.get_elo(away_code))
    if probs["home"] >= probs["away"]:
        fav, fav_elo, und_elo = home_code, home_elo, away_elo
    else:
        fav, fav_elo, und_elo = away_code, away_elo, home_elo
    return {
        "home_elo": home_elo,
        "away_elo": away_elo,
        "favorite_code": fav,
        "summary": f"{fav} favored — rating {fav_elo} vs {und_elo}",
        "pre_match": pre_probs or probs,
    }


async def enrich_match_probs(match: Match, events: list[dict] | None = None) -> dict:
    home = match.home_team
    away = match.away_team
    pre_probs = engine.pre_match_probabilities(home.code, away.code, neutral=True)
    timeline = events if events is not None else (match.events or [])

    if match.status == MatchStatus.LIVE and match.home_score is not None:
        probs = engine.live_probabilities(
            home.code,
            away.code,
            match.home_score,
            match.away_score or 0,
            match.minute or 0,
            timeline,
            neutral=True,
        )
    else:
        probs = pre_probs

    match.win_prob_home = probs["home"]
    match.win_prob_draw = probs["draw"]
    match.win_prob_away = probs["away"]
    return {"probs": probs, "pre_probs": pre_probs}


def match_to_dict(
    match: Match,
    pre_probs: dict[str, float] | None = None,
    *,
    events: list[dict] | None = None,
) -> dict:
    home = match.home_team
    away = match.away_team
    probs = {
        "home": match.win_prob_home or 0.33,
        "draw": match.win_prob_draw or 0.33,
        "away": match.win_prob_away or 0.33,
    }
    pre = pre_probs or probs
    timeline = events if events is not None else (match.events or [])
    return {
        "id": match.id,
        "home_team": {
            "id": home.id,
            "name": home.name,
            "code": home.code,
            "elo_rating": home.elo_rating,
            "group_letter": home.group_letter,
        },
        "away_team": {
            "id": away.id,
            "name": away.name,
            "code": away.code,
            "elo_rating": away.elo_rating,
            "group_letter": away.group_letter,
        },
        "home_score": match.home_score,
        "away_score": match.away_score,
        "minute": match.minute,
        "status": match.status.value,
        "stage": match.stage,
        "group_letter": match.group_letter,
        "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
        "local_date": match.local_date or match_calendar_date(match),
        "timezone": match.kickoff_timezone,
        "venue": match.venue,
        "city": match.city,
        "country": match.country,
        "events": timeline,
        "win_prob_home": match.win_prob_home,
        "win_prob_draw": match.win_prob_draw,
        "win_prob_away": match.win_prob_away,
        "model_context": _model_context(home.code, away.code, probs, pre),
    }


async def get_match_detail(db: AsyncSession, match_id: int) -> dict | None:
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.id == match_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        return None
    await migrate_json_events_if_needed(db, match)
    events = await fetch_events_for_match(db, match.id)
    enriched = await enrich_match_probs(match, events=events)
    data = match_to_dict(match, enriched["pre_probs"], events=events)
    row = await get_lineup_row(db, match.id)
    data.update(lineup_to_detail_fields(row))
    return data


async def get_all_matches(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"))
        .order_by(Match.kickoff_at)
    )
    matches = result.scalars().all()
    events_map = await fetch_events_by_match_ids(db, [m.id for m in matches])
    out = []
    for m in matches:
        events = events_map.get(m.id, [])
        if not events and m.events:
            await migrate_json_events_if_needed(db, m)
            events = await fetch_events_for_match(db, m.id)
        enriched = await enrich_match_probs(m, events=events)
        out.append(match_to_dict(m, enriched["pre_probs"], events=events))
    return out


async def get_match_days(db: AsyncSession) -> list[dict]:
    """Return sorted Eastern Time calendar dates with fixture counts."""
    result = await db.execute(
        select(Match)
        .where(Match.external_id.like(f"{OFFICIAL_EXTERNAL_PREFIX}%"))
        .order_by(Match.kickoff_at)
    )
    return summarize_match_days(result.scalars().all())


async def get_following_next(db: AsyncSession, team_ids: list[int]) -> list[dict]:
    """Next (or live) match for each followed team."""
    if not team_ids:
        return []

    out: list[dict] = []
    for tid in team_ids:
        result = await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(
                or_(Match.home_team_id == tid, Match.away_team_id == tid),
                Match.status.in_([MatchStatus.LIVE, MatchStatus.SCHEDULED]),
            )
            .order_by(Match.kickoff_at)
        )
        candidates = result.scalars().all()
        if not candidates:
            continue
        live = [m for m in candidates if m.status == MatchStatus.LIVE]
        pick = live[0] if live else candidates[0]
        events = await fetch_events_for_match(db, pick.id)
        enriched = await enrich_match_probs(pick, events=events)
        entry = match_to_dict(pick, enriched["pre_probs"], events=events)
        entry["followed_team_id"] = tid
        out.append(entry)
    return out


async def get_following_feed(db: AsyncSession, team_ids: list[int]) -> list[dict]:
    return await get_following_next(db, team_ids)


async def ensure_demo_live_match(db: AsyncSession) -> Match | None:
    """Ensure one IN_PLAY demo match exists (strong vs weak, score + events)."""
    live_result = await db.execute(
        select(Match).where(Match.status == MatchStatus.LIVE).limit(1)
    )
    if live_result.scalar_one_or_none():
        return None

    from app.services.fixtures_loader import opening_match_external_id

    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.external_id == opening_match_external_id())
    )
    target = result.scalar_one_or_none()
    if not target:
        result = await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(Match.status == MatchStatus.SCHEDULED)
            .order_by(Match.kickoff_at)
            .limit(1)
        )
        target = result.scalar_one_or_none()
    if not target:
        return None

    target.status = MatchStatus.LIVE
    target.home_score = 2
    target.away_score = 1
    target.minute = 58
    target.events = []
    await db.flush()
    await insert_new_events(db, target.id, _DEMO_SEED_EVENTS)
    await enrich_match_probs(target, events=await fetch_events_for_match(db, target.id))
    await db.flush()
    return target
