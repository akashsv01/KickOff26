"""Seed teams and fixtures from cached openfootball/worldcup.json."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, MatchStatus, Message, Room, Team
from app.services.fixtures_loader import (
    get_all_team_defs,
    get_fixtures_seed,
    get_official_group_map,
    opening_match_id,
)


async def seed_fixtures_from_json(
    db: AsyncSession,
    *,
    demo_live: bool = False,
    force: bool = False,
) -> dict:
    """Upsert all teams and published openfootball fixtures."""
    if not force:
        existing = await db.execute(select(Match).limit(1))
        if existing.scalar_one_or_none():
            return {"source": "openfootball", "skipped": True}

    official_groups = get_official_group_map()
    code_to_id: dict[str, int] = {}
    for t in get_all_team_defs():
        result = await db.execute(select(Team).where(Team.code == t["code"]))
        team = result.scalar_one_or_none()
        group = official_groups.get(t["code"]) or t.get("group")
        if team:
            team.name = t["name"]
            if group:
                team.group_letter = group
            if not t.get("placeholder"):
                team.elo_rating = t["elo"]
        else:
            team = Team(
                external_id=f"fixture-{t['code']}",
                name=t["name"],
                code=t["code"],
                group_letter=group,
                elo_rating=t.get("elo", 1500),
            )
            db.add(team)
        await db.flush()
        code_to_id[t["code"]] = team.id

    fixtures = get_fixtures_seed()
    valid_ids = {f["external_id"] for f in fixtures}

    stale_ids = [
        row[0]
        for row in (
            await db.execute(select(Match.id).where(Match.external_id.notin_(valid_ids)))
        ).all()
    ]
    if stale_ids:
        room_ids = select(Room.id).where(Room.match_id.in_(stale_ids))
        await db.execute(delete(Message).where(Message.room_id.in_(room_ids)))
        await db.execute(delete(Room).where(Room.match_id.in_(stale_ids)))
        await db.execute(delete(Match).where(Match.id.in_(stale_ids)))

    opening_id = opening_match_id()
    now = datetime.now(timezone.utc)
    match_count = 0
    live_seeded = False

    for f in fixtures:
        home_id = code_to_id.get(f["home_code"])
        away_id = code_to_id.get(f["away_code"])
        if not home_id or not away_id:
            continue

        status = MatchStatus.SCHEDULED
        home_score = None
        away_score = None
        minute = None
        events: list = []
        seed_events: list | None = None
        kickoff = f["kickoff_at"]
        local_date = f.get("local_date")
        kickoff_tz = f.get("timezone")

        if demo_live and f["external_id"] == opening_id:
            kickoff = now - timedelta(hours=1)
            # Keep official ET calendar day; only override clock/score for demo.
            status = MatchStatus.LIVE
            home_score = 2
            away_score = 1
            minute = 58
            seed_events = [
                {"type": "goal", "minute": 12, "team": "home", "player": "Jiménez"},
                {"type": "goal", "minute": 34, "team": "away", "player": "Promes"},
                {"type": "goal", "minute": 51, "team": "home", "player": "Lozano"},
                {"type": "yellow_card", "minute": 45, "team": "away", "player": "Mokoena"},
            ]
            live_seeded = True

        result = await db.execute(select(Match).where(Match.external_id == f["external_id"]))
        match = result.scalar_one_or_none()
        if match:
            match.home_team_id = home_id
            match.away_team_id = away_id
            match.kickoff_at = kickoff
            match.local_date = local_date
            match.kickoff_timezone = kickoff_tz
            match.venue = f["venue"]
            match.city = f["city"]
            match.country = f["country"]
            match.stadium_lat = f["lat"]
            match.stadium_lng = f["lng"]
            match.group_letter = f.get("group")
            match.stage = f["stage"]
            if force and f["external_id"] == opening_id and demo_live:
                match.status = status
                match.home_score = home_score
                match.away_score = away_score
                match.minute = minute
                match.events = []
        else:
            match = Match(
                external_id=f["external_id"],
                home_team_id=home_id,
                away_team_id=away_id,
                stage=f["stage"],
                group_letter=f.get("group"),
                kickoff_at=kickoff,
                local_date=local_date,
                kickoff_timezone=kickoff_tz,
                venue=f["venue"],
                city=f["city"],
                country=f["country"],
                stadium_lat=f["lat"],
                stadium_lng=f["lng"],
                status=status,
                home_score=home_score,
                away_score=away_score,
                minute=minute,
                events=[],
            )
            db.add(match)
        await db.flush()
        if seed_events and f["external_id"] == opening_id and demo_live:
            from app.services.match_events import insert_new_events

            await insert_new_events(db, match.id, seed_events)
        match_count += 1
    return {
        "source": "openfootball",
        "teams": len(code_to_id),
        "fixtures": match_count,
        "demo_live": live_seeded,
    }
