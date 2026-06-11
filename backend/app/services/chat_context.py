"""Retrieve real tournament + user context for the grounded AI assistant."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bracket, Team, User
from app.services.live_standings import compute_live_standings
from app.services.match_calendar import SCHEDULE_CALENDAR_TZ, match_calendar_date
from app.services.matchday import get_all_matches, get_following_next
from app.services.team_local_data import coach_from_local_json, player_to_watch_from_local_json
from app.services.team_roster_service import build_team_profile

MAX_CONTEXT_CHARS = 14_000

TOURNAMENT_META = """Tournament: FIFA World Cup 2026 (USA, Canada, Mexico).
Format: 48 teams in 12 groups (A–L), 4 teams per group. Top 2 in each group advance (24 teams).
Best 8 third-placed teams also advance (32-team Round of 32 knockout).
Group stage is round-robin; knockout is single elimination through the final."""

QUALIFICATION_RULE = """Best third-placed qualification (2026):
- After all group-stage matches, the 12 third-placed teams are ranked by: points, then goal difference, then goals scored.
- The top 8 of those 12 third-placed teams join the 24 automatic qualifiers (top 2 per group) in the Round of 32.
- Tiebreakers do not use head-to-head across groups for third-place ranking."""

_GROUP_RE = re.compile(r"\bgroup\s+([a-l])\b", re.I)
_TEAM_CODE_RE = re.compile(r"\b([A-Z]{3})\b")


def _truncate(text: str, limit: int = MAX_CONTEXT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n… [truncated]"


def _msg_lower(message: str) -> str:
    return message.lower()


def _wants_standings(msg: str) -> bool:
    return any(k in msg for k in ("standing", "table", "points", "rank", "leader", "qualif"))


def _wants_fixtures(msg: str) -> bool:
    return any(
        k in msg
        for k in (
            "fixture",
            "schedule",
            "match",
            "play",
            "kickoff",
            "kick-off",
            "when",
            "where",
            "venue",
            "today",
            "next",
            "live score",
            "score",
        )
    )


def _wants_team_info(msg: str) -> bool:
    return any(k in msg for k in ("coach", "squad", "roster", "player", "watch", "team"))


def _wants_bracket(msg: str) -> bool:
    return any(k in msg for k in ("bracket", "predict", "pick", "champion", "final", "knockout"))


def _wants_qualification(msg: str) -> bool:
    return any(k in msg for k in ("third", "qualification", "qualify", "advance", "round of 32", "r32"))


def _wants_groups(msg: str) -> bool:
    return "who" in msg and "group" in msg or "teams in group" in msg


def _groups_mentioned(msg: str) -> set[str]:
    return {m.group(1).upper() for m in _GROUP_RE.finditer(msg)}


async def _load_teams(db: AsyncSession) -> list[Team]:
    result = await db.execute(select(Team).order_by(Team.group_letter, Team.code))
    return list(result.scalars().all())


def _teams_mentioned(message: str, teams: list[Team]) -> list[Team]:
    msg = message.lower()
    found: list[Team] = []
    seen: set[int] = set()
    for team in teams:
        if team.id in seen:
            continue
        name = team.name.lower()
        code = team.code.lower()
        if code in msg or name in msg:
            found.append(team)
            seen.add(team.id)
    for match in _TEAM_CODE_RE.finditer(message):
        code = match.group(1).upper()
        for team in teams:
            if team.code == code and team.id not in seen:
                found.append(team)
                seen.add(team.id)
    return found


def _wants_global_schedule(msg: str) -> bool:
    """Tournament-wide schedule, not the user's followed teams."""
    if any(
        k in msg
        for k in (
            "in general",
            "overall",
            "world cup",
            "tournament",
            "any match",
            "not my",
            "not following",
            "everyone",
            "all teams",
        )
    ):
        return True
    if "next match" in msg and "my" not in msg and "follow" not in msg:
        return True
    return False


def _wants_followed_schedule(msg: str, user: User | None) -> bool:
    if not user:
        return False
    if _wants_global_schedule(msg):
        return False
    return any(k in msg for k in ("follow", "my team", "my teams", "favorite", "following"))


def _parse_kickoff_utc(m: dict) -> datetime | None:
    raw = m.get("kickoff_at")
    if not raw:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_match_line(m: dict) -> str:
    home = m.get("home_team") or {}
    away = m.get("away_team") or {}
    cal = match_calendar_date(m)
    kickoff = m.get("kickoff_at") or m.get("local_date")
    parts = [
        f"{home.get('name')} ({home.get('code')}) vs {away.get('name')} ({away.get('code')})",
        f"status={m.get('status')}",
        f"calendar_date_et={cal}",
        f"kickoff_utc={kickoff}",
    ]
    if m.get("group_letter"):
        parts.append(f"group={m.get('group_letter')}")
    if m.get("venue"):
        loc = m.get("city") or ""
        parts.append(f"venue={m.get('venue')}" + (f", {loc}" if loc else ""))
    if m.get("status") in ("live", "finished"):
        parts.append(f"score={m.get('home_score')}-{m.get('away_score')}")
        if m.get("minute") is not None:
            parts.append(f"minute={m.get('minute')}")
    return " | ".join(parts)


def build_schedule_snapshot(matches: list[dict], now: datetime | None = None) -> dict:
    """Compute authoritative live / next / today buckets for the assistant."""
    now = now or datetime.now(timezone.utc)
    today_et = now.astimezone(SCHEDULE_CALENDAR_TZ).date().isoformat()

    live = [m for m in matches if m.get("status") == "live"]
    live.sort(key=lambda m: _parse_kickoff_utc(m) or now)

    upcoming: list[dict] = []
    for m in matches:
        if m.get("status") == "live":
            upcoming.append(m)
            continue
        if m.get("status") != "scheduled":
            continue
        kickoff = _parse_kickoff_utc(m)
        if kickoff is None or kickoff >= now:
            upcoming.append(m)
    upcoming.sort(key=lambda m: _parse_kickoff_utc(m) or now)

    next_match = upcoming[0] if upcoming else None

    today_matches = [
        m
        for m in matches
        if match_calendar_date(m) == today_et and m.get("status") in ("scheduled", "live")
    ]
    today_matches.sort(key=lambda m: _parse_kickoff_utc(m) or now)

    return {
        "now_utc": now.isoformat(),
        "today_et": today_et,
        "live": live,
        "next_match": next_match,
        "today_matches": today_matches,
    }


def _format_schedule_snapshot(snapshot: dict, *, global_focus: bool) -> str:
    lines = [
        "Schedule snapshot (authoritative — use this for 'next match' / 'today' questions):",
        f"  Current time UTC: {snapshot['now_utc']}",
        f"  Today's calendar date (Eastern, official schedule): {snapshot['today_et']}",
    ]
    if global_focus:
        lines.append(
            "  Note: user asked for tournament-wide schedule — do NOT answer from followed-team lists."
        )

    if snapshot["live"]:
        lines.append("  LIVE NOW:")
        for m in snapshot["live"]:
            lines.append(f"    • {_format_match_line(m)}")

    if snapshot["next_match"]:
        lines.append("  NEXT TOURNAMENT MATCH (by kickoff time, excluding finished):")
        lines.append(f"    • {_format_match_line(snapshot['next_match'])}")

    if snapshot["today_matches"]:
        lines.append("  Other matches on today's calendar date (ET):")
        for m in snapshot["today_matches"][:10]:
            if m is snapshot["next_match"] and len(snapshot["today_matches"]) == 1:
                continue
            if snapshot["next_match"] and m.get("id") == snapshot["next_match"].get("id"):
                continue
            lines.append(f"    • {_format_match_line(m)}")

    if not snapshot["live"] and not snapshot["next_match"]:
        lines.append("  No live or upcoming matches found in app data.")
    return "\n".join(lines)


def _compact_match(m: dict) -> dict:
    home = m.get("home_team") or {}
    away = m.get("away_team") or {}
    row: dict[str, Any] = {
        "id": m.get("id"),
        "home": home.get("code"),
        "away": away.get("code"),
        "kickoff": m.get("kickoff_at") or m.get("local_date"),
        "status": m.get("status"),
        "group": m.get("group_letter"),
        "venue": m.get("venue"),
        "city": m.get("city"),
    }
    if m.get("status") in ("live", "finished"):
        row["score"] = f"{m.get('home_score')}-{m.get('away_score')}"
        if m.get("minute") is not None:
            row["minute"] = m.get("minute")
    return row


def _format_standings(data: dict, groups_filter: set[str] | None = None) -> str:
    lines = ["Current group standings (live data):"]
    for grp in data.get("groups") or []:
        letter = grp.get("group")
        if groups_filter and letter not in groups_filter:
            continue
        live_tag = " [LIVE]" if grp.get("live") else ""
        lines.append(f"\nGroup {letter}{live_tag}:")
        for row in grp.get("rows") or []:
            qual = row.get("qualification")
            badge = ""
            if qual == "auto":
                badge = " Q"
            elif qual == "third":
                badge = " 3rd"
            lines.append(
                f"  {row.get('rank')}. {row.get('code')} — "
                f"{row.get('points')} pts, GD {row.get('gd', 0)}, "
                f"GF {row.get('gf', 0)}, GA {row.get('ga', 0)}{badge}"
            )
    best = data.get("best_thirds") or []
    if best and (not groups_filter or _wants_qualification("third")):
        lines.append(f"\nCurrent best-third candidates (top 8 codes): {', '.join(best)}")
    return "\n".join(lines)


def _format_matches(
    matches: list[dict],
    *,
    teams: list[Team],
    msg: str,
    today: str,
    global_schedule: bool,
) -> str:
    codes = {t.code for t in teams}
    msg_l = msg.lower()
    filtered = matches
    if codes and not global_schedule:
        filtered = [
            m
            for m in matches
            if (m.get("home_team") or {}).get("code") in codes
            or (m.get("away_team") or {}).get("code") in codes
        ]
    if "today" in msg_l:
        filtered = [m for m in filtered if match_calendar_date(m) == today]
    if "live" in msg_l:
        live = [m for m in filtered if m.get("status") == "live"]
        if live:
            filtered = live
    if not filtered and teams and not global_schedule:
        filtered = matches
    if not filtered:
        return "Fixtures: no matching fixtures found in app data."
    compact = [_compact_match(m) for m in filtered[:24]]
    return "Additional fixtures (reference only — prefer Schedule snapshot for 'next match'):\n" + json.dumps(
        compact, indent=2
    )


async def _user_bracket_summary(db: AsyncSession, user: User) -> str:
    result = await db.execute(
        select(Bracket)
        .where(Bracket.user_id == user.id, Bracket.mode == "manual")
        .order_by(Bracket.updated_at.desc())
        .limit(1)
    )
    bracket = result.scalar_one_or_none()
    if not bracket or not bracket.picks:
        return "User saved bracket: none saved yet."

    picks = bracket.picks
    lines = [f"User saved bracket ({bracket.name or 'My Bracket'}):"]
    knockout = picks.get("knockout") or {}
    if knockout.get("final-1") or picks.get("final"):
        champ = knockout.get("final-1") or picks.get("final")
        lines.append(f"  Predicted champion: {champ}")
    if knockout:
        key_picks = {k: v for k, v in knockout.items() if k in ("final-1", "sf-1", "sf-2", "qf-1", "qf-2", "r32-1")}
        if key_picks:
            lines.append(f"  Key knockout picks: {json.dumps(key_picks)}")
    group_results = picks.get("group_results") or {}
    if group_results:
        lines.append(f"  Group-stage results entered: {len(group_results)} match(es)")
    return "\n".join(lines)


async def _user_context(db: AsyncSession, user: User, *, include_followed_schedule: bool = True) -> str:
    lines = [
        "Current user context (only share with this user — never other users' data):",
        f"  Username: {user.username}",
    ]
    if user.country_region:
        lines.append(f"  Country/region (from signup): {user.country_region}")
    if user.preferred_language:
        lines.append(f"  Preferred language: {user.preferred_language}")

    team_ids = list(user.followed_team_ids or [])
    if user.favorite_team_id and user.favorite_team_id not in team_ids:
        team_ids.insert(0, user.favorite_team_id)

    if team_ids:
        result = await db.execute(select(Team).where(Team.id.in_(team_ids)))
        followed = {t.id: t for t in result.scalars().all()}
        names = [f"{followed[tid].name} ({followed[tid].code})" for tid in team_ids if tid in followed]
        if names:
            lines.append(f"  Followed teams: {', '.join(names)}")
        if include_followed_schedule:
            next_matches = await get_following_next(db, team_ids)
            if next_matches:
                lines.append("  Next/upcoming for user's followed teams (personalized only):")
                for m in next_matches[:6]:
                    lines.append(f"    - {_format_match_line(m)}")
    else:
        lines.append("  Followed teams: none selected")

    lines.append(await _user_bracket_summary(db, user))
    return "\n".join(lines)


async def _format_team_profile(db: AsyncSession, team: Team) -> str:
    profile = await build_team_profile(db, team, allow_fetch=False)
    coach = profile.get("coach") or coach_from_local_json(team)
    ptw = profile.get("player_to_watch") or player_to_watch_from_local_json(team)
    lines = [
        f"Team {team.name} ({team.code}), Group {team.group_letter}:",
        f"  Coach: {coach or profile.get('coach_display') or 'not in app data'}",
    ]
    if ptw:
        lines.append(f"  Player to watch: {ptw.get('player')} — {ptw.get('reason', '')}")
    squad = profile.get("squad") or {}
    if squad.get("status") == "ready":
        by_pos = squad.get("players_by_position") or {}
        total = sum(len(v) for v in by_pos.values())
        lines.append(f"  Squad: {total} players cached in app")
    else:
        lines.append("  Squad: not yet loaded in app")
    return "\n".join(lines)


def _format_groups(teams: list[Team]) -> str:
    by_group: dict[str, list[str]] = {}
    for t in teams:
        g = t.group_letter or "?"
        by_group.setdefault(g, []).append(f"{t.name} ({t.code})")
    lines = ["Teams by group:"]
    for g in sorted(by_group.keys()):
        lines.append(f"  Group {g}: {', '.join(sorted(by_group[g]))}")
    return "\n".join(lines)


async def build_chat_context(
    db: AsyncSession,
    message: str,
    user: User | None,
) -> str:
    """Assemble grounded context from Postgres for the user's question."""
    msg = _msg_lower(message)
    sections = [TOURNAMENT_META]

    teams = await _load_teams(db)
    mentioned = _teams_mentioned(message, teams)
    groups_filter = _groups_mentioned(message)
    global_schedule = _wants_global_schedule(msg)

    if user:
        sections.append(
            await _user_context(
                db,
                user,
                include_followed_schedule=_wants_followed_schedule(msg, user),
            )
        )
    else:
        sections.append(
            "User: guest (not logged in). "
            "Personalized answers about saved bracket picks or followed teams require login."
        )

    standings_data: dict | None = None
    if _wants_standings(msg) or groups_filter or _wants_qualification(msg):
        standings_data = await compute_live_standings(db)
        sections.append(_format_standings(standings_data, groups_filter or None))

    if _wants_qualification(msg):
        sections.append(QUALIFICATION_RULE)

    if _wants_groups(msg) or groups_filter:
        if groups_filter:
            filtered = [t for t in teams if t.group_letter in groups_filter]
            sections.append(_format_groups(filtered if filtered else teams))
        else:
            sections.append(_format_groups(teams))

    if _wants_fixtures(msg) or mentioned or (user and _wants_followed_schedule(msg, user)):
        all_matches = await get_all_matches(db)
        now = datetime.now(timezone.utc)
        today_et = now.astimezone(SCHEDULE_CALENDAR_TZ).date().isoformat()
        snapshot = build_schedule_snapshot(all_matches, now)
        sections.append(_format_schedule_snapshot(snapshot, global_focus=global_schedule))
        target_teams = mentioned
        if user and _wants_followed_schedule(msg, user):
            ids = list(user.followed_team_ids or [])
            if user.favorite_team_id:
                ids = list(dict.fromkeys([user.favorite_team_id, *ids]))
            if ids:
                result = await db.execute(select(Team).where(Team.id.in_(ids)))
                target_teams = list(result.scalars().all())
        sections.append(
            _format_matches(
                all_matches,
                teams=target_teams,
                msg=msg,
                today=today_et,
                global_schedule=global_schedule or not target_teams,
            )
        )

    if _wants_team_info(msg) or mentioned:
        for team in mentioned[:5]:
            sections.append(await _format_team_profile(db, team))

    if user and _wants_bracket(msg):
        sections.append(await _user_bracket_summary(db, user))

    return _truncate("\n\n".join(sections))
