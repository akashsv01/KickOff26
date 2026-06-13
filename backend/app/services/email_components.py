"""Shared, email-client-safe building blocks for KickOff26 emails.

Both the welcome email and the daily digest render through these helpers so the
branding, flag/logo images, timezone-labeled time formatting, and match-row
layout stay identical and live in one place. Everything is table-based with
inline CSS (email clients ignore <style>/flexbox/grid) and degrades gracefully
when images are blocked (alt text + 3-letter code always read cleanly).

IP-safe: original KickOff26 wordmark + icon (never the real trophy), country
flags only (never crests). Real data only - callers pass DB fixtures.
"""

from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import Match, MatchStatus

# --- Palette (inline; dark theme with a light-mode-safe explicit background) ---
GOLD = "#f5c451"
GOLD_DEEP = "#c9a227"
HEADER_BG = "#0b1220"
BODY_BG = "#0a0f1a"
CARD_BG = "#121a2b"
ROW_BG = "#0e1626"
TEXT = "#e8edf5"
MUTED = "#9aa7b8"
BORDER = "#1f2b41"


def safe_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def logo_url() -> str:
    base = settings.app_base_url.rstrip("/")
    return settings.email_logo_url.strip() or f"{base}/icon-192.png"


def profile_url() -> str:
    return f"{settings.app_base_url.rstrip('/')}/profile"


# --------------------------------------------------------------------------- #
# Time + date formatting (shared with the app's timezone-aware display)
# --------------------------------------------------------------------------- #

def zone_abbr(local_dt: datetime) -> str:
    """Short zone label that MATCHES the displayed clock time (e.g. IST, GMT+5:30)."""
    return local_dt.strftime("%Z") or "UTC"


def fmt_date_long(local_dt: datetime) -> str:
    """'Saturday, 13 June 2026' (no leading zero on the day)."""
    return f"{local_dt:%A}, {local_dt.day} {local_dt:%B %Y}"


def fmt_date_short(local_dt: datetime) -> str:
    """'13 Jun' for subject lines."""
    return f"{local_dt.day} {local_dt:%b}"


def fmt_kickoff(dt: datetime, zone: ZoneInfo) -> str:
    """'6:30 AM IST' - clock time and zone label in the user's timezone, consistent."""
    local = dt.astimezone(zone)
    clock = local.strftime("%I:%M %p").lstrip("0")
    return f"{clock} {zone_abbr(local)}"


# --------------------------------------------------------------------------- #
# Teams / flags
# --------------------------------------------------------------------------- #

def _team_name(team) -> str:
    return html.escape(str(getattr(team, "name", None) or getattr(team, "code", None) or "TBD"))


def _team_code(team) -> str:
    return html.escape(str(getattr(team, "code", None) or "TBD")).upper()


def _flag_img(team, *, size: int = 24) -> str:
    """Hosted flag <img> (flags only). Empty string when no flag - caller shows code."""
    url = getattr(team, "flag_url", None)
    if not url:
        return ""
    name = str(getattr(team, "name", None) or getattr(team, "code", None) or "")
    return (
        f'<img src="{html.escape(url)}" width="{size}" alt="{html.escape(name)} flag" '
        f'style="vertical-align:middle;border-radius:3px;border:1px solid {BORDER};" />'
    )


def _match_meta(match: Match, zone: ZoneInfo) -> str:
    """Final/live score for played matches, otherwise the zone-labeled kickoff time."""
    status = match.status
    if status == MatchStatus.FINISHED:
        return f"{match.home_score or 0} - {match.away_score or 0} &middot; FT"
    if status == MatchStatus.LIVE and match.home_score is not None:
        minute = f"{match.minute}'" if match.minute else "LIVE"
        return f"{match.home_score or 0} - {match.away_score or 0} &middot; {minute}"
    if match.kickoff_at is not None:
        return fmt_kickoff(match.kickoff_at, zone)
    return "Time TBD"


def match_card(match: Match, zone: ZoneInfo, *, highlight: bool = False) -> str:
    """A polished match row: FlagA TeamA  vs  TeamB FlagB, with time/score beneath."""
    home, away = match.home_team, match.away_team
    home_flag, away_flag = _flag_img(home), _flag_img(away)
    border = GOLD if highlight else BORDER
    return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 0 10px;background:{CARD_BG};border:1px solid {border};border-radius:10px;">
  <tr>
    <td align="right" width="42%" style="padding:14px 8px 4px 14px;color:{TEXT};font-size:15px;font-weight:600;">
      {_team_name(home)} <span style="color:{MUTED};font-weight:700;">{_team_code(home)}</span> {home_flag}
    </td>
    <td align="center" width="16%" style="padding:14px 0 4px;color:{MUTED};font-size:12px;font-weight:700;letter-spacing:1px;">VS</td>
    <td align="left" width="42%" style="padding:14px 14px 4px 8px;color:{TEXT};font-size:15px;font-weight:600;">
      {away_flag} <span style="color:{MUTED};font-weight:700;">{_team_code(away)}</span> {_team_name(away)}
    </td>
  </tr>
  <tr>
    <td colspan="3" align="center" style="padding:0 14px 14px;color:{GOLD};font-size:13px;font-weight:700;font-variant-numeric:tabular-nums;">
      {_match_meta(match, zone)}
    </td>
  </tr>
</table>"""


def section_heading(text: str) -> str:
    return (
        f'<h2 style="margin:22px 0 12px;color:{TEXT};font-size:16px;'
        f'border-left:3px solid {GOLD};padding-left:10px;">{html.escape(text)}</h2>'
    )


def matches_section(title: str, matches: list[Match], zone: ZoneInfo, *, highlight_first: bool = False) -> str:
    """Heading + a card per match (ordered as given). Empty list -> nothing."""
    if not matches:
        return ""
    cards = [
        match_card(m, zone, highlight=highlight_first and i == 0)
        for i, m in enumerate(matches)
    ]
    return section_heading(title) + "".join(cards)


def empty_note(text: str) -> str:
    return f'<p style="margin:8px 0 0;color:{MUTED};font-size:15px;line-height:1.6;">{html.escape(text)}</p>'


def paragraph(text: str) -> str:
    return f'<p style="margin:0 0 16px;color:{MUTED};font-size:15px;line-height:1.6;">{html.escape(text)}</p>'


def cta_button(label: str, href: str) -> str:
    return (
        f'<p style="margin:18px 0 4px;"><a href="{html.escape(href)}" '
        f'style="display:inline-block;background:{GOLD};color:#0a0f1a;font-weight:700;'
        f'font-size:14px;text-decoration:none;padding:10px 18px;border-radius:8px;">'
        f'{html.escape(label)}</a></p>'
    )


# --------------------------------------------------------------------------- #
# Shell + footers
# --------------------------------------------------------------------------- #

def render_email(*, preheader: str, heading: str, subheading_html: str, body_html: str, footer_html: str) -> str:
    """Wrap content in the dark/gold KickOff26 shell (logo + wordmark header)."""
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:{BODY_BG};font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(preheader)}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BODY_BG};padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
          <tr>
            <td style="background:{HEADER_BG};border:1px solid {BORDER};border-bottom:3px solid {GOLD};border-radius:12px 12px 0 0;padding:20px 28px;">
              <img src="{html.escape(logo_url())}" width="34" height="34" alt="KickOff26" style="vertical-align:middle;border:0;" />
              <span style="vertical-align:middle;font-size:22px;font-weight:800;letter-spacing:0.5px;color:{GOLD};padding-left:8px;">KickOff<span style="color:{TEXT};">26</span></span>
            </td>
          </tr>
          <tr>
            <td style="background:{BODY_BG};border:1px solid {BORDER};border-top:0;padding:28px;">
              <h1 style="margin:0 0 6px;color:{TEXT};font-size:22px;">{html.escape(heading)}</h1>
              <div style="color:{MUTED};font-size:14px;line-height:1.6;margin-bottom:18px;">{subheading_html}</div>
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="background:{HEADER_BG};border:1px solid {BORDER};border-top:0;border-radius:0 0 12px 12px;padding:18px 28px;">
              {footer_html}
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def _footer_shell(lines_html: str) -> str:
    return f'<p style="margin:0;color:{MUTED};font-size:12px;line-height:1.7;">{lines_html}</p>'


def welcome_footer() -> str:
    base = settings.app_base_url.rstrip("/")
    return _footer_shell(
        f'<a href="{base}" style="color:{GOLD_DEEP};text-decoration:none;">{html.escape(base)}</a><br/>'
        "You are receiving this because you signed up for KickOff26. "
        f'<a href="{profile_url()}" style="color:{GOLD_DEEP};">Manage email preferences</a>.'
    )


def digest_footer() -> str:
    """Includes the working unsubscribe/manage link (points at the /profile toggle)."""
    return _footer_shell(
        "You are receiving this because you opted into the KickOff26 daily digest.<br/>"
        f'<a href="{profile_url()}" style="color:{GOLD_DEEP};font-weight:700;">Unsubscribe or manage preferences</a> '
        "(turn off the daily digest on your profile)."
    )
