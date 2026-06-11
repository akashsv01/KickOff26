from datetime import datetime, timedelta, timezone

import pytest

from app.services.itinerary import (
    _estimate_travel_hours,
    _haversine_km,
    get_host_cities,
    optimize_itinerary,
)
from app.services.ticket_estimates import estimate_ticket_range


@pytest.fixture
def sample_matches():
    base = datetime(2026, 6, 15, 18, 0, tzinfo=timezone.utc)
    return [
        {
            "id": 1,
            "home_code": "USA",
            "away_code": "MEX",
            "kickoff_at": base,
            "city": "Los Angeles",
            "country": "USA",
            "venue": "SoFi Stadium",
            "lat": 33.953,
            "lng": -118.339,
            "stage": "group",
        },
        {
            "id": 2,
            "home_code": "USA",
            "away_code": "CAN",
            "kickoff_at": datetime(2026, 6, 22, 18, 0, tzinfo=timezone.utc),
            "city": "Seattle",
            "country": "USA",
            "venue": "Lumen Field",
            "lat": 47.595,
            "lng": -122.332,
            "stage": "group",
        },
        {
            "id": 3,
            "home_code": "BRA",
            "away_code": "ARG",
            "kickoff_at": datetime(2026, 6, 28, 18, 0, tzinfo=timezone.utc),
            "city": "Mexico City",
            "country": "Mexico",
            "venue": "Estadio Azteca",
            "lat": 19.303,
            "lng": -99.151,
            "stage": "group",
        },
    ]


def test_optimize_itinerary_returns_stops(sample_matches):
    plan = optimize_itinerary(sample_matches, {"USA"}, max_cities=5)
    assert len(plan["stops"]) >= 1
    assert plan["stops"][0]["city"] == "Los Angeles"
    assert plan["stops"][0]["ticket_estimate"]["display_range"].startswith("$")


def test_multi_city_itinerary(sample_matches):
    plan = optimize_itinerary(sample_matches, {"USA", "BRA"}, max_cities=5)
    cities = {s["city"] for s in plan["stops"]}
    assert len(cities) >= 2
    assert plan["total_travel_hours"] > 0


def test_travel_hours_from_distance():
    km = _haversine_km(33.953, -118.339, 47.595, -122.332)
    hours = _estimate_travel_hours(km)
    assert km > 1000
    assert hours > 3


def test_budget_uses_ticket_high_end(sample_matches):
    plan = optimize_itinerary(sample_matches, {"BRA"}, max_cities=5, budget_usd=500)
    assert plan["total_ticket_cost_high_usd"] <= 500
    assert plan["total_ticket_cost_high_usd"] > 0 or any("budget" in n.lower() for n in plan["notes"])


def test_cross_border_note(sample_matches):
    plan = optimize_itinerary(sample_matches, {"USA", "BRA"}, max_cities=5)
    cross_border = [s for s in plan["stops"] if s.get("cross_border_note")]
    if len(plan["stops"]) >= 3:
        assert len(cross_border) >= 1


def test_host_cities_count():
    cities = get_host_cities()
    assert len(cities) == 16


def test_ticket_range_group_host():
    t = estimate_ticket_range("group", "USA", "PAR")
    assert t["low_usd"] == 355
    assert t["high_usd"] == 2735


def test_ticket_range_group_non_host():
    t = estimate_ticket_range("group", "BRA", "ARG")
    assert t["low_usd"] == 120
    assert t["high_usd"] == 410


def test_disclaimer_present(sample_matches):
    plan = optimize_itinerary(sample_matches, {"USA"}, max_cities=3)
    assert "dynamic" in plan["disclaimer"].lower()


def test_only_followed_team_matches_in_plan(sample_matches):
    plan = optimize_itinerary(sample_matches, {"USA"}, max_cities=5)
    for stop in plan["stops"]:
        label = stop["match_label"]
        assert "USA" in label
    assert all("BRA" not in s["match_label"] for s in plan["stops"])


def test_maximizes_attendable_matches_when_feasible():
    matches = [
        {
            "id": i,
            "home_code": "USA",
            "away_code": "MEX",
            "kickoff_at": datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc) + timedelta(days=7 * (i - 1)),
            "city": city,
            "country": "USA",
            "venue": f"Stadium {i}",
            "lat": lat,
            "lng": lng,
            "stage": "group",
        }
        for i, (city, lat, lng) in enumerate(
            [
                ("Los Angeles", 33.953, -118.339),
                ("Seattle", 47.595, -122.332),
                ("Dallas", 32.747, -97.094),
                ("Atlanta", 33.755, -84.401),
            ],
            start=1,
        )
    ]
    plan = optimize_itinerary(matches, {"USA"}, max_cities=4, budget_usd=None)
    assert len(plan["stops"]) == 4


def test_skip_reason_mentions_max_cities():
    cities = [
        ("Los Angeles", 33.953, -118.339),
        ("Seattle", 47.595, -122.332),
        ("Dallas", 32.747, -97.094),
    ]
    matches = [
        {
            "id": i,
            "home_code": "USA",
            "away_code": "MEX",
            "kickoff_at": datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc) + timedelta(days=7 * (i - 1)),
            "city": city,
            "country": "USA",
            "venue": f"Stadium {i}",
            "lat": lat,
            "lng": lng,
            "stage": "group",
        }
        for i, (city, lat, lng) in enumerate(cities, start=1)
    ]
    plan = optimize_itinerary(matches, {"USA"}, max_cities=2, budget_usd=None)
    assert len({s["city"] for s in plan["stops"]}) <= 2
    skipped = [n for n in plan["notes"] if n.startswith("Skipped")]
    assert any("max cities" in n.lower() for n in skipped)


def test_skip_reason_mentions_budget(sample_matches):
    plan = optimize_itinerary(sample_matches, {"USA", "BRA"}, max_cities=5, budget_usd=400)
    skipped = [n for n in plan["notes"] if n.startswith("Skipped")]
    assert any("budget" in n.lower() for n in skipped)


def test_skip_reason_mentions_travel_time():
    base = datetime(2026, 6, 15, 18, 0, tzinfo=timezone.utc)
    matches = [
        {
            "id": 1,
            "home_code": "USA",
            "away_code": "MEX",
            "kickoff_at": base,
            "city": "Los Angeles",
            "country": "USA",
            "venue": "SoFi Stadium",
            "lat": 33.953,
            "lng": -118.339,
            "stage": "group",
        },
        {
            "id": 2,
            "home_code": "USA",
            "away_code": "CAN",
            "kickoff_at": datetime(2026, 6, 15, 22, 0, tzinfo=timezone.utc),
            "city": "Seattle",
            "country": "USA",
            "venue": "Lumen Field",
            "lat": 47.595,
            "lng": -122.332,
            "stage": "group",
        },
    ]
    plan = optimize_itinerary(matches, {"USA"}, max_cities=5, budget_usd=None)
    skipped = [n for n in plan["notes"] if n.startswith("Skipped")]
    assert len(plan["stops"]) == 1
    assert any("not enough time" in n.lower() or "travel" in n.lower() for n in skipped)
