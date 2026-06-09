"""
Estimated FIFA World Cup 2026 ticket price RANGES (USD).

These are NOT official FIFA prices. FIFA uses dynamic pricing; actual sale prices
vary by match, category, and demand. Ranges below are grounded in publicly reported
2026 figures from sports/business press coverage (e.g. supporter tier through Category 1
and knockout-round reporting). Use only as planning estimates.

Sources summarized in project docs — update when FIFA publishes final categories.
"""

from __future__ import annotations

HOST_NATION_CODES = frozenset({"USA", "MEX", "CAN"})

# stage key -> (low_usd, high_usd, human label)
STAGE_TICKET_RANGES: dict[str, tuple[int, int, str]] = {
    # Non-host group: ~$60 supporter to ~$620 Cat 1 → representative planning band
    "group": (120, 410, "Group stage"),
    # Host-nation group matches (USA/Mexico/Canada): higher reported band
    "group_host": (355, 2735, "Group stage (host nation)"),
    "r32": (105, 750, "Round of 32"),
    "r16": (170, 980, "Round of 16"),
    "qf": (275, 1775, "Quarter-final"),
    "sf": (420, 3295, "Semi-final"),
    "third": (275, 1775, "Third-place match"),
    "final": (420, 6730, "Final"),
}

FANPLAN_PRICE_DISCLAIMER = (
    "Ticket prices shown are estimates based on published reporting for FIFA World Cup 2026. "
    "FIFA uses dynamic pricing — actual prices vary at purchase."
)

TRAVEL_TIME_DISCLAIMER = (
    "Travel times are estimates from great-circle distance and average ground/flight speeds, "
    "not real-time schedules."
)


def estimate_ticket_range(stage: str, home_code: str, away_code: str) -> dict:
    """Return low/high USD range and display label for a fixture."""
    stage_key = stage or "group"
    if stage_key == "group":
        if home_code in HOST_NATION_CODES or away_code in HOST_NATION_CODES:
            low, high, label = STAGE_TICKET_RANGES["group_host"]
        else:
            low, high, label = STAGE_TICKET_RANGES["group"]
    else:
        low, high, label = STAGE_TICKET_RANGES.get(
            stage_key,
            STAGE_TICKET_RANGES["group"],
        )

    return {
        "low_usd": low,
        "high_usd": high,
        "label": label,
        "display_range": f"est. ${low:,}–${high:,}",
        "is_estimate": True,
    }
