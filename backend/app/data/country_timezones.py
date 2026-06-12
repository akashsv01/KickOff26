"""Country -> representative IANA timezone map for the signup viewer countries.

Keys are the EXACT display labels used by the signup country dropdown
(frontend/lib/signupProfile.ts -> SIGNUP_COUNTRIES) and stored on
``User.country_region``. Multi-zone countries use the capital / most-populous
zone. "Other" and any unlisted/blank country intentionally have no entry, so
they fall through to the browser-detected timezone (stored at signup), then UTC.
"""

from __future__ import annotations

# Display label -> one representative IANA zone.
COUNTRY_TIMEZONE: dict[str, str] = {
    # Multi-zone: capital / most-populous zone
    "United States": "America/New_York",
    "Canada": "America/Toronto",
    "Mexico": "America/Mexico_City",
    "Brazil": "America/Sao_Paulo",
    "Australia": "Australia/Sydney",
    "Indonesia": "Asia/Jakarta",
    # Single-zone (effectively)
    "United Kingdom": "Europe/London",
    "Argentina": "America/Argentina/Buenos_Aires",
    "Germany": "Europe/Berlin",
    "France": "Europe/Paris",
    "Spain": "Europe/Madrid",
    "Italy": "Europe/Rome",
    "Netherlands": "Europe/Amsterdam",
    "Portugal": "Europe/Lisbon",
    "Belgium": "Europe/Brussels",
    "Switzerland": "Europe/Zurich",
    "Poland": "Europe/Warsaw",
    "Sweden": "Europe/Stockholm",
    "Norway": "Europe/Oslo",
    "Denmark": "Europe/Copenhagen",
    "Turkey": "Europe/Istanbul",
    "Saudi Arabia": "Asia/Riyadh",
    "United Arab Emirates": "Asia/Dubai",
    "Qatar": "Asia/Qatar",
    "Egypt": "Africa/Cairo",
    "Morocco": "Africa/Casablanca",
    "South Africa": "Africa/Johannesburg",
    "Nigeria": "Africa/Lagos",
    "India": "Asia/Kolkata",
    "China": "Asia/Shanghai",
    "Japan": "Asia/Tokyo",
    "South Korea": "Asia/Seoul",
    "Colombia": "America/Bogota",
    "Chile": "America/Santiago",
}

DEFAULT_TIMEZONE = "UTC"


def timezone_for_country(country: str | None) -> str | None:
    """Return the representative IANA zone for a stored country label, or None."""
    if not country:
        return None
    return COUNTRY_TIMEZONE.get(country.strip())


def default_signup_timezone(country: str | None, browser_tz: str | None) -> str | None:
    """Timezone to STORE at signup.

    A known country wins (India -> Asia/Kolkata), so an explicit country choice
    is honored over the auto-detected browser zone. The browser zone is only a
    fallback for "Other"/unlisted countries; otherwise None (resolves to UTC).
    """
    mapped = timezone_for_country(country)
    if mapped:
        return mapped
    browser = (browser_tz or "").strip()
    return browser or None


def resolve_timezone(user) -> str:
    """Best-effort IANA timezone for a user.

    Order: ``user.timezone`` (set at signup via ``default_signup_timezone`` -
    country zone for known countries, browser zone for "Other"/unlisted - or
    later edited in the profile), then the country map (``user.country_region``),
    then UTC.
    """
    explicit = (getattr(user, "timezone", None) or "").strip()
    if explicit:
        return explicit
    mapped = timezone_for_country(getattr(user, "country_region", None))
    if mapped:
        return mapped
    return DEFAULT_TIMEZONE
