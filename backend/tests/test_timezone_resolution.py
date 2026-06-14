"""resolve_timezone precedence: a chosen country overrides the browser zone."""

from __future__ import annotations

from types import SimpleNamespace

from app.data.country_timezones import default_signup_timezone, resolve_timezone


def _user(country, timezone):
    return SimpleNamespace(country_region=country, timezone=timezone)


def test_known_country_overrides_stored_browser_zone():
    # India chosen, browser detected America/New_York -> country wins.
    assert resolve_timezone(_user("India", "America/New_York")) == "Asia/Kolkata"
    assert resolve_timezone(_user("Japan", "America/New_York")) == "Asia/Tokyo"


def test_other_or_null_country_uses_browser_zone():
    assert resolve_timezone(_user("Other", "America/Los_Angeles")) == "America/Los_Angeles"
    assert resolve_timezone(_user(None, "Europe/London")) == "Europe/London"


def test_falls_back_to_utc():
    assert resolve_timezone(_user(None, None)) == "UTC"
    assert resolve_timezone(_user("Other", None)) == "UTC"


def test_signup_default_stores_country_zone_for_known_country():
    assert default_signup_timezone("Japan", "America/New_York") == "Asia/Tokyo"
    assert default_signup_timezone("Other", "America/New_York") == "America/New_York"
    assert default_signup_timezone(None, None) is None
