from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_optional_user
from app.db import get_db
from app.models import Bracket, Match, MatchStatus, Team, User
from app.schemas import BracketPicksResponse, BracketResponse, BracketSaveRequest, SimulateRequest
from app.services.match_resolver import resolve_match_probs
from app.services.poster import generate_champion_poster
from app.services.sim_job_manager import SimJobConflictError, sim_job_manager
from app.services.simulator import get_group_match_probs
from app.services.tournament_2026 import KNOCKOUT_ROUNDS

router = APIRouter(prefix="/bracket", tags=["bracket"])


def _compute_group_standings(matches: list[Match]) -> dict[str, list[dict]]:
    """Build standings tables from finished group-stage results."""
    tables: dict[str, dict[str, dict]] = {}

    for m in matches:
        if m.status != MatchStatus.FINISHED or not m.group_letter:
            continue
        g = m.group_letter
        tables.setdefault(g, {})
        for side, team in (("home", m.home_team), ("away", m.away_team)):
            if team.code not in tables[g]:
                tables[g][team.code] = {
                    "code": team.code,
                    "name": team.name,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "gf": 0,
                    "ga": 0,
                    "points": 0,
                }
        hs = m.home_score or 0
        aws = m.away_score or 0
        home = tables[g][m.home_team.code]
        away = tables[g][m.away_team.code]
        home["played"] += 1
        away["played"] += 1
        home["gf"] += hs
        home["ga"] += aws
        away["gf"] += aws
        away["ga"] += hs
        if hs > aws:
            home["won"] += 1
            home["points"] += 3
            away["lost"] += 1
        elif hs < aws:
            away["won"] += 1
            away["points"] += 3
            home["lost"] += 1
        else:
            home["drawn"] += 1
            away["drawn"] += 1
            home["points"] += 1
            away["points"] += 1

    result: dict[str, list[dict]] = {}
    for g, rows in tables.items():
        sorted_rows = sorted(
            rows.values(),
            key=lambda r: (r["points"], r["gf"] - r["ga"], r["gf"]),
            reverse=True,
        )
        for i, row in enumerate(sorted_rows, start=1):
            row["rank"] = i
            row["gd"] = row["gf"] - row["ga"]
        result[g] = sorted_rows
    return result


@router.get("/structure")
async def get_structure(db: AsyncSession = Depends(get_db)):
    """Full bracket layout: groups, fixtures, standings, knockout rounds."""
    from app.services.tournament_2026 import OFFICIAL_TEAMS

    official_codes = {t["code"] for t in OFFICIAL_TEAMS}
    team_result = await db.execute(
        select(Team).where(Team.code.in_(official_codes)).order_by(Team.group_letter, Team.code)
    )
    teams = team_result.scalars().all()
    groups: dict[str, list] = {}
    code_to_team: dict[str, dict] = {}
    for t in teams:
        g = t.group_letter or "?"
        groups.setdefault(g, []).append(
            {"id": t.id, "name": t.name, "code": t.code, "elo": t.elo_rating}
        )
        code_to_team[t.code] = {"id": t.id, "name": t.name, "code": t.code, "elo": t.elo_rating}

    match_result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.stage == "group")
        .order_by(Match.kickoff_at)
    )
    group_matches = match_result.scalars().all()
    fixtures_by_group: dict[str, list] = {}
    for m in group_matches:
        g = m.group_letter or "?"
        fixtures_by_group.setdefault(g, []).append(
            {
                "id": m.id,
                "home": {"code": m.home_team.code, "name": m.home_team.name},
                "away": {"code": m.away_team.code, "name": m.away_team.name},
                "kickoff_at": m.kickoff_at.isoformat() if m.kickoff_at else None,
                "city": m.city,
                "venue": m.venue,
                "status": m.status.value,
                "home_score": m.home_score,
                "away_score": m.away_score,
            }
        )

    standings = _compute_group_standings(group_matches)
    for g, team_list in groups.items():
        if g not in standings:
            standings[g] = [
                {
                    "code": t["code"],
                    "name": t["name"],
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "gf": 0,
                    "ga": 0,
                    "gd": 0,
                    "points": 0,
                    "rank": i,
                }
                for i, t in enumerate(team_list, start=1)
            ]

    knockout = []
    for rnd in KNOCKOUT_ROUNDS:
        slots = []
        for i in range(1, rnd["matches"] + 1):
            slots.append({"slot": f"{rnd['id']}-{i}", "label": f"Match {i}"})
        knockout.append({"id": rnd["id"], "label": rnd["label"], "slots": slots})

    return {
        "groups": groups,
        "fixtures": fixtures_by_group,
        "standings": standings,
        "knockout": knockout,
        "teams_by_code": code_to_team,
        "match_odds": get_group_match_probs(),
    }


@router.get("/groups")
async def get_groups(db: AsyncSession = Depends(get_db)):
    """Return teams organized by group with match odds."""
    from app.services.tournament_2026 import OFFICIAL_TEAMS

    official_codes = {t["code"] for t in OFFICIAL_TEAMS}
    result = await db.execute(
        select(Team).where(Team.code.in_(official_codes)).order_by(Team.group_letter, Team.code)
    )
    teams = result.scalars().all()
    groups: dict[str, list] = {}
    for t in teams:
        g = t.group_letter or "?"
        groups.setdefault(g, []).append(
            {"id": t.id, "name": t.name, "code": t.code, "elo": t.elo_rating}
        )
    odds = get_group_match_probs()
    return {"groups": groups, "match_odds": odds}


@router.get("/odds/{home_code}/{away_code}")
async def get_match_odds(home_code: str, away_code: str):
    probs = resolve_match_probs(home_code.upper(), away_code.upper(), neutral=True)
    return {"home": probs["home"], "draw": probs["draw"], "away": probs["away"]}


async def _get_manual_bracket(db: AsyncSession, user_id: int) -> Bracket | None:
    result = await db.execute(
        select(Bracket)
        .where(Bracket.user_id == user_id, Bracket.mode == "manual")
        .order_by(Bracket.updated_at.desc(), Bracket.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _upsert_manual_bracket(
    db: AsyncSession,
    user_id: int,
    name: str,
    picks: dict,
) -> Bracket:
    champion_id = await _extract_champion(picks, db)
    existing = await _get_manual_bracket(db, user_id)
    if existing:
        existing.name = name
        existing.picks = picks
        existing.champion_team_id = champion_id
        await db.flush()
        await db.refresh(existing)
        return existing

    bracket = Bracket(
        user_id=user_id,
        name=name,
        mode="manual",
        picks=picks,
        champion_team_id=champion_id,
    )
    db.add(bracket)
    await db.flush()
    await db.refresh(bracket)
    return bracket


def _merge_picks(existing: dict | None, partial: dict) -> dict:
    merged = dict(existing or {})
    merged.update(partial)
    return merged


def _meaningful_picks(picks: dict) -> bool:
    """True if picks contain any saved group or knockout data."""
    if not picks:
        return False
    if picks.get("group_results"):
        return True
    if picks.get("knockout"):
        return True
    if picks.get("slot_teams"):
        return True
    return False


@router.post("/save", response_model=BracketResponse)
async def save_bracket(
    data: BracketSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert the user's manual bracket picks (full payload — group + knockout)."""
    bracket = await _upsert_manual_bracket(db, user.id, data.name, data.picks)
    return BracketResponse.model_validate(bracket)


@router.post("/save/groups", response_model=BracketResponse)
async def save_group_picks(
    data: BracketSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist group-stage results and R32 seeding; keeps existing knockout picks."""
    existing = await _get_manual_bracket(db, user.id)
    current = dict(existing.picks) if existing and existing.picks else {}
    merged = _merge_picks(
        current,
        {
            "version": data.picks.get("version", current.get("version", 2)),
            "group_results": data.picks.get("group_results") or {},
            "slot_teams": data.picks.get("slot_teams") or {},
        },
    )
    bracket = await _upsert_manual_bracket(db, user.id, data.name, merged)
    return BracketResponse.model_validate(bracket)


@router.post("/save/knockout", response_model=BracketResponse)
async def save_knockout_picks(
    data: BracketSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist knockout advancement picks; keeps existing group-stage results."""
    existing = await _get_manual_bracket(db, user.id)
    current = dict(existing.picks) if existing and existing.picks else {}
    merged = _merge_picks(
        current,
        {
            "version": data.picks.get("version", current.get("version", 2)),
            "knockout": data.picks.get("knockout") or {},
        },
    )
    bracket = await _upsert_manual_bracket(db, user.id, data.name, merged)
    return BracketResponse.model_validate(bracket)


@router.get("/picks", response_model=BracketPicksResponse)
async def get_saved_picks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return the user's latest saved manual picks (empty dict if none)."""
    bracket = await _get_manual_bracket(db, user.id)
    if not bracket or not bracket.picks:
        return BracketPicksResponse(picks={}, updated_at=None)
    return BracketPicksResponse(picks=bracket.picks, updated_at=bracket.updated_at)


@router.delete("/picks")
async def clear_saved_picks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Delete all saved manual bracket picks for this user."""
    result = await db.execute(
        select(Bracket).where(Bracket.user_id == user.id, Bracket.mode == "manual")
    )
    deleted = 0
    for bracket in result.scalars().all():
        await db.delete(bracket)
        deleted += 1
    await db.flush()
    return {"deleted": deleted}


@router.delete("/picks/groups")
async def clear_group_picks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Clear saved group-stage results only; knockout picks are preserved."""
    bracket = await _get_manual_bracket(db, user.id)
    if not bracket or not bracket.picks:
        return {"cleared": "groups", "remaining": False}

    picks = dict(bracket.picks)
    picks.pop("group_results", None)
    picks.pop("slot_teams", None)

    if not _meaningful_picks(picks):
        await db.delete(bracket)
        await db.flush()
        return {"cleared": "groups", "remaining": False}

    bracket.picks = picks
    bracket.champion_team_id = await _extract_champion(picks, db)
    await db.flush()
    return {"cleared": "groups", "remaining": True}


@router.delete("/picks/knockout")
async def clear_knockout_picks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Clear saved knockout advancement picks only; group results are preserved."""
    bracket = await _get_manual_bracket(db, user.id)
    if not bracket or not bracket.picks:
        return {"cleared": "knockout", "remaining": False}

    picks = dict(bracket.picks)
    picks.pop("knockout", None)

    if not _meaningful_picks(picks):
        await db.delete(bracket)
        await db.flush()
        return {"cleared": "knockout", "remaining": False}

    bracket.picks = picks
    bracket.champion_team_id = None
    await db.flush()
    return {"cleared": "knockout", "remaining": True}


@router.get("/mine", response_model=list[BracketResponse])
async def my_brackets(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Bracket).where(Bracket.user_id == user.id).order_by(Bracket.updated_at.desc())
    )
    return [BracketResponse.model_validate(b) for b in result.scalars().all()]


from app.services.leaderboard import score_brackets


@router.post("/leaderboard/rescore")
async def rescore(db: AsyncSession = Depends(get_db)):
    count = await score_brackets(db)
    return {"updated": count}


@router.get("/leaderboard")
async def leaderboard(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Bracket, User.username)
        .join(User)
        .where(Bracket.mode == "manual", Bracket.accuracy_score.isnot(None))
        .order_by(Bracket.accuracy_score.desc())
        .limit(50)
    )
    return [
        {"username": username, "accuracy_score": b.accuracy_score, "name": b.name}
        for b, username in result.all()
    ]


def _sim_user_key(user: User | None, request_client: str | None = None) -> str:
    if user:
        return f"user:{user.id}"
    return f"anon:{request_client or 'unknown'}"


@router.post("/simulate")
async def simulate(
    data: SimulateRequest,
    user: User | None = Depends(get_optional_user),
):
    """Start a Live Monte Carlo job — returns immediately; progress over WebSocket."""
    try:
        job = await sim_job_manager.create_job(data.iterations, _sim_user_key(user), mode="live")
    except SimJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "task_id": job.job_id,
        "channel": job.channel,
        "iterations": job.iterations,
        "status": job.status.value,
    }


@router.post("/simulate/quick")
async def simulate_quick(
    data: SimulateRequest,
    user: User | None = Depends(get_optional_user),
):
    """Start a Quick Monte Carlo job — poll GET /simulate/jobs/{task_id} for results."""
    try:
        job = await sim_job_manager.create_job(data.iterations, _sim_user_key(user), mode="quick")
    except SimJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "task_id": job.job_id,
        "iterations": job.iterations,
        "status": job.status.value,
    }


@router.post("/simulate/sync")
async def simulate_sync_legacy(
    data: SimulateRequest,
    user: User | None = Depends(get_optional_user),
):
    """Legacy alias — starts a Quick job (non-blocking). Poll /simulate/jobs/{task_id}."""
    return await simulate_quick(data, user)


@router.get("/simulate/jobs/{job_id}")
async def get_simulation_job(job_id: str):
    """Poll simulation status, progress, and final result."""
    job = sim_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Simulation job not found")

    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "iterations": job.iterations,
        "progress": job.progress,
        "result": job.result if job.status.value == "complete" else None,
        "error": job.error,
        "channel": job.channel if job.mode == "live" else None,
    }


@router.get("/poster/{team_code}")
async def champion_poster(team_code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Team).where(Team.code == team_code.upper()))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    png = generate_champion_poster(team.name, team.code)
    return Response(content=png, media_type="image/png")


async def _extract_champion(picks: dict, db: AsyncSession) -> int | None:
    knockout = picks.get("knockout") or {}
    code = knockout.get("final-1") or picks.get("final")
    if not code:
        return None
    if isinstance(code, int):
        return code
    result = await db.execute(select(Team).where(Team.code == str(code).upper()))
    team = result.scalar_one_or_none()
    return team.id if team else None
