"""Canonical MatchDay alert + event types (API-Football free tier + app-derived).

Both LIVE_DATA_MODE=api and demo must use only these types so behavior matches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import Match
from app.services.squads import get_squad_player_names
from app.websocket.gateway import ws_manager

PROB_SHIFT_THRESHOLD = 0.15  # 15% swing triggers momentum alert
UNKNOWN_PLAYER = "Unknown player"


def normalize_player_name(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return UNKNOWN_PLAYER
    return str(raw).strip()

if TYPE_CHECKING:
    pass

# Stored on Match.events JSON
SUPPORTED_EVENT_TYPES = frozenset(
    {"goal", "yellow_card", "red_card", "substitution", "penalty", "var"}
)

# WebSocket matches:alerts payloads
SUPPORTED_ALERT_TYPES = frozenset(
    {
        "goal_alert",
        "yellow_card_alert",
        "red_card_alert",
        "substitution_alert",
        "penalty_alert",
        "var_alert",
        "match_start_alert",
        "match_halftime_alert",
        "match_end_alert",
        "momentum_alert",
    }
)

# Events that trigger accelerated API polling
BURST_EVENT_TYPES = frozenset({"goal", "red_card", "penalty", "var"})

EVENT_TO_ALERT = {
    "goal": "goal_alert",
    "yellow_card": "yellow_card_alert",
    "red_card": "red_card_alert",
    "substitution": "substitution_alert",
    "penalty": "penalty_alert",
    "var": "var_alert",
}


def is_supported_event(event: dict) -> bool:
    return event.get("type") in SUPPORTED_EVENT_TYPES


def filter_supported_events(events: list[dict]) -> list[dict]:
    return [e for e in events if is_supported_event(e)]


def event_key(ev: dict) -> tuple:
    return (
        ev.get("type"),
        ev.get("minute"),
        ev.get("team"),
        ev.get("player"),
        ev.get("detail"),
    )


def diff_new_events(old: list[dict], new: list[dict]) -> list[dict]:
    seen = {event_key(e) for e in filter_supported_events(old or [])}
    return [e for e in filter_supported_events(new) if event_key(e) not in seen]


def parse_api_events(
    raw_events: list[dict],
    api_home_id: int,
) -> list[dict]:
    """Normalize API-Football events; drop unsupported play-by-play (corners, fouls, etc.)."""
    out: list[dict] = []
    for ev in raw_events:
        minute = (ev.get("time") or {}).get("elapsed") or 0
        team_side = "home" if (ev.get("team") or {}).get("id") == api_home_id else "away"
        player = normalize_player_name((ev.get("player") or {}).get("name"))
        ev_type = (ev.get("type") or "").lower()
        detail = (ev.get("detail") or "").lower()
        comments = (ev.get("comments") or "").lower()

        if ev_type == "goal":
            if "missed penalty" in detail or "missed penalty" in comments:
                out.append(
                    {
                        "type": "penalty",
                        "minute": minute,
                        "team": team_side,
                        "player": player,
                        "detail": "missed",
                    }
                )
            elif "penalty" in detail:
                out.append(
                    {
                        "type": "penalty",
                        "minute": minute,
                        "team": team_side,
                        "player": player,
                        "detail": "scored",
                    }
                )
            else:
                out.append(
                    {"type": "goal", "minute": minute, "team": team_side, "player": player}
                )
        elif ev_type == "card":
            if "red" in detail:
                out.append(
                    {"type": "red_card", "minute": minute, "team": team_side, "player": player}
                )
            elif "yellow" in detail:
                out.append(
                    {
                        "type": "yellow_card",
                        "minute": minute,
                        "team": team_side,
                        "player": player,
                    }
                )
        elif ev_type in ("subst", "substitution"):
            assist = normalize_player_name((ev.get("assist") or {}).get("name"))
            entry: dict = {
                "type": "substitution",
                "minute": minute,
                "team": team_side,
                "player": player,
            }
            if assist != UNKNOWN_PLAYER:
                entry["detail"] = f"on for {assist}"
            out.append(entry)
        elif ev_type == "var":
            var_detail = ev.get("detail") or "VAR decision"
            out.append(
                {
                    "type": "var",
                    "minute": minute,
                    "team": team_side,
                    "player": player,
                    "detail": var_detail,
                }
            )
        # Ignore: corners, fouls, shots, offside, free kicks, etc.
    return out


def format_event_message(match: Match, event: dict) -> str:
    team_label = match.home_team.code if event.get("team") == "home" else match.away_team.code
    minute = event.get("minute", 0)
    player = event.get("player") or UNKNOWN_PLAYER
    ev_type = event["type"]
    detail = event.get("detail") or ""

    if ev_type == "goal":
        return (
            f"GOAL! {team_label} ({player}) — "
            f"{match.home_score}-{match.away_score} {minute}'"
        )
    if ev_type == "yellow_card":
        return f"YELLOW CARD — {team_label} ({player}) {minute}'"
    if ev_type == "red_card":
        return f"RED CARD — {team_label} ({player}) {minute}'"
    if ev_type == "substitution":
        sub_detail = f" ({detail})" if detail else ""
        return f"SUBSTITUTION — {team_label}: {player}{sub_detail} {minute}'"
    if ev_type == "penalty":
        if detail == "missed":
            return f"PENALTY MISSED — {team_label} ({player}) {minute}'"
        return (
            f"PENALTY GOAL — {team_label} ({player}) — "
            f"{match.home_score}-{match.away_score} {minute}'"
        )
    if ev_type == "var":
        return f"VAR — {detail} ({team_label}) {minute}'"
    return f"{ev_type} — {team_label} {minute}'"


def build_event_alert(match: Match, event: dict) -> dict:
    alert_type = EVENT_TO_ALERT[event["type"]]
    return {
        "type": alert_type,
        "match_id": match.id,
        "message": format_event_message(match, event),
        "team": event.get("team"),
        "minute": event.get("minute"),
        "event_type": event["type"],
    }


async def broadcast_alert(alert: dict, match_id: int) -> None:
    if alert.get("type") not in SUPPORTED_ALERT_TYPES:
        return
    await ws_manager.broadcast("matches:alerts", alert)
    await ws_manager.broadcast(ws_manager.match_channel(match_id), alert)


async def emit_event_alerts(match: Match, new_events: list[dict]) -> bool:
    """Alert on newly ingested supported events. Returns True if burst-worthy."""
    burst = False
    for ev in new_events:
        if not is_supported_event(ev):
            continue
        if ev["type"] in BURST_EVENT_TYPES:
            burst = True
        await broadcast_alert(build_event_alert(match, ev), match.id)
    return burst


async def emit_status_alert(match: Match, alert_type: str, message: str) -> None:
    if alert_type not in SUPPORTED_ALERT_TYPES:
        return
    await broadcast_alert({"type": alert_type, "match_id": match.id, "message": message}, match.id)


async def emit_prob_momentum(
    match: Match,
    old_probs: dict[str, float],
    new_probs: dict[str, float],
) -> None:
    for side in ("home", "draw", "away"):
        shift = abs(new_probs[side] - old_probs.get(side, 0))
        if shift >= PROB_SHIFT_THRESHOLD:
            await broadcast_alert(
                {
                    "type": "momentum_alert",
                    "match_id": match.id,
                    "message": (
                        f"{match.home_team.code} vs {match.away_team.code}: "
                        f"{side} win % moved {shift:.0%} → {new_probs[side]:.0%}"
                    ),
                    "probs": new_probs,
                    "shift": shift,
                },
                match.id,
            )


def demo_pick_event() -> str | None:
    """Weighted random supported event type for demo mode (no unsupported play-by-play)."""
    import random

    roll = random.random()
    if roll < 0.10:
        return "goal"
    if roll < 0.13:
        return "yellow_card"
    if roll < 0.15:
        return "red_card"
    if roll < 0.19:
        return "substitution"
    if roll < 0.205:
        return "penalty"
    if roll < 0.22:
        return "var"
    return None


def demo_build_event(
    ev_type: str,
    minute: int,
    team: str,
    *,
    home_code: str | None = None,
    away_code: str | None = None,
) -> dict:
    import random

    team_code = home_code if team == "home" else away_code
    pool = get_squad_player_names(team_code or "")
    player = random.choice(pool)
    event: dict = {"type": ev_type, "minute": minute, "team": team, "player": player}
    if ev_type == "penalty":
        event["detail"] = "scored" if random.random() < 0.75 else "missed"
    elif ev_type == "var":
        event["detail"] = random.choice(
            ["Penalty confirmed", "Goal cancelled", "No penalty", "Review completed"]
        )
        event["player"] = UNKNOWN_PLAYER
    elif ev_type == "substitution":
        others = [n for n in pool if n != player]
        event["detail"] = f"on for {random.choice(others)}" if others else "on for teammate"
    return event
