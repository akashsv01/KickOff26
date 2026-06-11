"""Itinerary optimizer for fan travel across 16 host cities - real fixtures, estimated costs."""

from __future__ import annotations

import math
from datetime import datetime

from app.services.ticket_estimates import (
    FANPLAN_PRICE_DISCLAIMER,
    TRAVEL_TIME_DISCLAIMER,
    estimate_ticket_range,
)
from app.services.tournament_2026 import HOST_CITIES

# Travel time heuristics (clearly estimates - not airline schedules)
GROUND_THRESHOLD_KM = 300
GROUND_SPEED_KMH = 80
FLIGHT_EFFECTIVE_SPEED_KMH = 700
GROUND_OVERHEAD_H = 1.0
FLIGHT_OVERHEAD_H = 2.5
MIN_HOURS_BEFORE_KICKOFF = 4.0

CROSS_BORDER_NOTE = (
    "Cross-border travel: {from_country} → {to_country}. "
    "Bring passport; allow extra time at immigration. "
    "ESTA/eTA may be required for US/Canada entry."
)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def _estimate_travel_hours(km: float) -> float:
    """Estimated door-to-door travel time from distance (not a live schedule)."""
    if km < 1:
        return 0.0
    if km < GROUND_THRESHOLD_KM:
        return km / GROUND_SPEED_KMH + GROUND_OVERHEAD_H
    return km / FLIGHT_EFFECTIVE_SPEED_KMH + FLIGHT_OVERHEAD_H


def _cross_border_note(from_country: str, to_country: str) -> str | None:
    if from_country == to_country:
        return None
    return CROSS_BORDER_NOTE.format(from_country=from_country, to_country=to_country)


def _valid_coords(lat: float, lng: float) -> bool:
    return abs(lat) > 0.01 and abs(lng) > 0.01


def _resolve_coords(city: str, lat: float | None, lng: float | None) -> tuple[float, float]:
    if lat and lng and _valid_coords(lat, lng):
        return float(lat), float(lng)
    info = HOST_CITIES.get(city or "")
    if info:
        return float(info["lat"]), float(info["lng"])
    return 0.0, 0.0


def _ticket_high_total(path: list[dict]) -> int:
    return sum(m["_ticket"]["high_usd"] for m in path)


def _ticket_low_total(path: list[dict]) -> int:
    return sum(m["_ticket"]["low_usd"] for m in path)


def _cities_in_path(path: list[dict]) -> set[str]:
    return {m["city"] for m in path}


def _can_add_match(
    path: list[dict],
    match: dict,
    max_cities: int,
    budget_usd: float | None,
) -> bool:
    return _skip_reason(path, match, max_cities, budget_usd) is None


def _skip_reason(
    path: list[dict],
    match: dict,
    max_cities: int,
    budget_usd: float | None,
) -> str | None:
    """Return a short reason if `match` cannot follow `path`; else None."""
    cities = _cities_in_path(path)
    if match["city"] not in cities and len(cities) >= max_cities:
        return f"would exceed max cities ({max_cities})"

    if budget_usd is not None:
        projected_high = _ticket_high_total(path) + match["_ticket"]["high_usd"]
        if projected_high > budget_usd:
            remaining = max(budget_usd - _ticket_high_total(path), 0)
            return (
                f"estimated tickets ({match['_ticket']['display_range']}) "
                f"exceed remaining budget (est. ${remaining:,.0f} left at high end)"
            )

    if not path:
        return None

    prev = path[-1]
    km = _haversine_km(prev["lat"], prev["lng"], match["lat"], match["lng"])
    travel_h = _estimate_travel_hours(km)

    prev_kick = prev.get("kickoff_at")
    curr_kick = match.get("kickoff_at")
    if prev_kick and curr_kick:
        gap_h = (curr_kick - prev_kick).total_seconds() / 3600
        if gap_h < travel_h + MIN_HOURS_BEFORE_KICKOFF:
            return (
                f"not enough time after previous match "
                f"(est. {travel_h:.1f}h travel + {MIN_HOURS_BEFORE_KICKOFF:.0f}h buffer needed)"
            )

    return None


def _match_label(m: dict) -> str:
    return f"{m['city']} ({m['home_code']} vs {m['away_code']})"


def _select_best_path(
    relevant: list[dict],
    max_cities: int,
    budget_usd: float | None,
) -> tuple[list[dict], list[str]]:
    """
    Maximize matches attendable in chronological order under city, budget, and travel constraints.
    Uses O(n^2) dynamic programming - never stops early when a longer feasible path exists.
    """
    notes: list[str] = []
    n = len(relevant)
    if n == 0:
        return [], notes

    dp = [0] * n
    paths: list[list[int]] = [[] for _ in range(n)]

    for j in range(n):
        if _can_add_match([], relevant[j], max_cities, budget_usd):
            dp[j] = 1
            paths[j] = [j]

        for i in range(j):
            if dp[i] == 0:
                continue
            candidate = paths[i] + [j]
            if _can_add_match([relevant[k] for k in paths[i]], relevant[j], max_cities, budget_usd):
                if len(candidate) > dp[j]:
                    dp[j] = len(candidate)
                    paths[j] = candidate

    valid_ends = [idx for idx in range(n) if dp[idx] > 0]
    if not valid_ends:
        for m in relevant:
            reason = _skip_reason([], m, max_cities, budget_usd) or "does not fit your constraints"
            notes.append(f"Skipped {_match_label(m)} - {reason}.")
        return [], notes

    best_end = max(
        valid_ends,
        key=lambda idx: (dp[idx], -_ticket_high_total([relevant[k] for k in paths[idx]])),
    )
    best = [relevant[i] for i in paths[best_end]]
    selected_ids = {m["id"] for m in best}

    for m in relevant:
        if m["id"] in selected_ids:
            continue

        prefix = [
            s
            for s in best
            if s.get("kickoff_at") and m.get("kickoff_at") and s["kickoff_at"] < m["kickoff_at"]
        ]
        reason = _skip_reason(prefix, m, max_cities, budget_usd)
        if reason is None:
            reason = _skip_reason(best, m, max_cities, budget_usd) or (
                "other chosen matches fill your route more completely"
            )

        notes.append(f"Skipped {_match_label(m)} - {reason}.")

    cities_used = _cities_in_path(best)
    if best and len(cities_used) >= max_cities:
        notes.append(f"Itinerary uses {len(cities_used)} of {max_cities} allowed host cities.")

    return best, notes


def _build_stop(match: dict, prev: dict | None) -> dict:
    travel_km = None
    travel_h = None
    border_note = None

    if prev is not None:
        travel_km = round(_haversine_km(prev["lat"], prev["lng"], match["lat"], match["lng"]), 1)
        travel_h = round(_estimate_travel_hours(travel_km), 2)
        if prev["country"] != match["country"]:
            border_note = _cross_border_note(prev["country"], match["country"])

    ticket = match["_ticket"]
    return {
        "city": match["city"],
        "country": match["country"],
        "match_id": match["id"],
        "match_label": f"{match['home_code']} vs {match['away_code']}",
        "stadium": match["venue"],
        "stage": match.get("stage") or "group",
        "kickoff_at": match.get("kickoff_at"),
        "lat": match["lat"],
        "lng": match["lng"],
        "travel_from_prev_km": travel_km,
        "travel_from_prev_hours": travel_h,
        "travel_is_estimate": travel_h is not None,
        "ticket_estimate": ticket,
        "cross_border_note": border_note,
    }


def optimize_itinerary(
    matches: list[dict],
    team_codes: set[str],
    max_cities: int = 5,
    budget_usd: float | None = None,
) -> dict:
    """
    Build a multi-city fan itinerary from real fixtures involving followed teams.

    Uses haversine distance for inter-city travel estimates and published ticket
    price ranges (labeled estimates). Budget compares against high end of ticket ranges.
    """
    enriched: list[dict] = []
    for m in matches:
        if m["home_code"] not in team_codes and m["away_code"] not in team_codes:
            continue
        lat, lng = _resolve_coords(m.get("city", ""), m.get("lat"), m.get("lng"))
        if not _valid_coords(lat, lng):
            continue
        stage = m.get("stage") or "group"
        ticket = estimate_ticket_range(stage, m["home_code"], m["away_code"])
        enriched.append(
            {
                **m,
                "lat": lat,
                "lng": lng,
                "stage": stage,
                "_ticket": ticket,
            }
        )

    if not enriched:
        return _empty_plan(["No matches found for selected teams with valid host-city coordinates."])

    enriched.sort(key=lambda m: m.get("kickoff_at") or datetime.min)

    selected, notes = _select_best_path(enriched, max_cities, budget_usd)
    if not selected:
        msg = "No feasible itinerary for your constraints."
        if budget_usd is not None:
            msg += f" Try raising the budget above ${budget_usd:,.0f} (estimates use ticket range high end)."
        return _empty_plan([msg, *notes])

    stops = []
    total_travel_h = 0.0
    total_travel_km = 0.0
    for i, m in enumerate(selected):
        prev = selected[i - 1] if i > 0 else None
        stop = _build_stop(m, prev)
        if stop["travel_from_prev_hours"]:
            total_travel_h += stop["travel_from_prev_hours"]
        if stop["travel_from_prev_km"]:
            total_travel_km += stop["travel_from_prev_km"]
        stops.append(stop)

    return {
        "stops": stops,
        "total_ticket_cost_low_usd": _ticket_low_total(selected),
        "total_ticket_cost_high_usd": _ticket_high_total(selected),
        "total_travel_hours": round(total_travel_h, 2),
        "total_travel_km": round(total_travel_km, 1),
        "disclaimer": f"{FANPLAN_PRICE_DISCLAIMER} {TRAVEL_TIME_DISCLAIMER}",
        "notes": notes,
        # Legacy field: high-end ticket total for older clients
        "total_cost_usd": float(_ticket_high_total(selected)),
    }


def _empty_plan(notes: list[str]) -> dict:
    return {
        "stops": [],
        "total_ticket_cost_low_usd": 0,
        "total_ticket_cost_high_usd": 0,
        "total_travel_hours": 0.0,
        "total_travel_km": 0.0,
        "disclaimer": FANPLAN_PRICE_DISCLAIMER,
        "notes": notes,
        "total_cost_usd": 0.0,
    }


def get_host_cities() -> dict:
    """Return host city metadata for map rendering."""
    return {
        city: {
            "country": info["country"],
            "lat": info["lat"],
            "lng": info["lng"],
            "stadium": info["stadium"],
        }
        for city, info in HOST_CITIES.items()
    }
