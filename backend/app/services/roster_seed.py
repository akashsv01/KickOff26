"""Seed team_rosters from bundled Zafronix export (team_rosters_2026.json).

Rosters fetched once from Zafronix and bundled as team_rosters_2026.json;
app serves from DB/file, no live polling (free tier 250 req/day).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Team, TeamRoster
from app.services.team_name_resolve import (
    local_json_key_for_team,
    normalize_lookup_key,
    zafronix_slug_for_team,
)
from app.services.tournament_2026 import OFFICIAL_TEAMS

logger = logging.getLogger(__name__)

ROSTER_BUNDLE_PATH = Path(__file__).resolve().parents[2] / "data" / "team_rosters_2026.json"
_OFFICIAL_CODES = {t["code"] for t in OFFICIAL_TEAMS}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_fetched_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f %z",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            return datetime.strptime(text.replace("+00:00", "+0000"), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_roster_bundle(path: Path | None = None) -> list[dict]:
    bundle_path = path or ROSTER_BUNDLE_PATH
    if not bundle_path.is_file():
        raise FileNotFoundError(f"Roster bundle not found: {bundle_path}")
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("team_rosters_2026.json must be a JSON array")
    return data


def _slug_index(entries: list[dict]) -> dict[str, dict]:
    """Index bundle rows by normalized zafronix_slug (prefer ready + players)."""
    index: dict[str, dict] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        slug = row.get("zafronix_slug")
        if not slug:
            continue
        key = normalize_lookup_key(str(slug))
        existing = index.get(key)
        if existing is None:
            index[key] = row
            continue
        row_ready = row.get("fetch_status") == "ready" and bool(row.get("players"))
        existing_ready = existing.get("fetch_status") == "ready" and bool(existing.get("players"))
        if row_ready and not existing_ready:
            index[key] = row
    return index


def roster_lookup_keys_for_team(team: Team) -> list[str]:
    """Slug/name variants used to find a team in the bundled roster export."""
    keys: list[str] = []
    for value in (
        zafronix_slug_for_team(team),
        team.name,
        local_json_key_for_team(team),
    ):
        if value and value not in keys:
            keys.append(value)
    return keys


def find_roster_bundle_entry(team: Team, index: dict[str, dict]) -> dict | None:
    for key in roster_lookup_keys_for_team(team):
        entry = index.get(normalize_lookup_key(key))
        if entry is not None:
            return entry
    return None


async def seed_team_rosters_from_bundle(
    db: AsyncSession,
    *,
    path: Path | None = None,
    force: bool = True,
) -> dict:
    """
    Upsert official-team rosters from team_rosters_2026.json (idempotent).

    Matches teams via zafronix_slug / name aliases — not team_id in the file.
    """
    entries = load_roster_bundle(path)
    index = _slug_index(entries)

    teams = (
        await db.execute(
            select(Team).where(Team.code.in_(_OFFICIAL_CODES)).order_by(Team.group_letter, Team.code)
        )
    ).scalars().all()

    stats = {
        "teams": len(teams),
        "seeded": 0,
        "skipped": 0,
        "ready": 0,
        "unavailable": 0,
        "missing": [],
    }

    for team in teams:
        entry = find_roster_bundle_entry(team, index)
        if entry is None:
            stats["missing"].append(team.code)
            logger.warning("Roster bundle: no entry for %s (%s)", team.code, team.name)
            continue

        row = (
            await db.execute(select(TeamRoster).where(TeamRoster.team_id == team.id))
        ).scalar_one_or_none()

        players = list(entry.get("players") or [])
        status = "ready" if players else "unavailable"

        if (
            not force
            and row
            and row.fetch_status == "ready"
            and row.players
            and len(row.players) == len(players)
        ):
            stats["skipped"] += 1
            if status == "ready":
                stats["ready"] += 1
            else:
                stats["unavailable"] += 1
            continue

        if row is None:
            row = TeamRoster(team_id=team.id)
            db.add(row)

        row.zafronix_slug = entry.get("zafronix_slug") or zafronix_slug_for_team(team)
        row.players = players
        row.coach = entry.get("coach")
        row.fetch_status = status
        row.error_message = entry.get("error_message") if not players else None
        row.fetched_at = _parse_fetched_at(entry.get("fetched_at")) or _utcnow()
        row.retry_after = None
        await db.flush()

        stats["seeded"] += 1
        if status == "ready":
            stats["ready"] += 1
        else:
            stats["unavailable"] += 1

    logger.info(
        "Roster bundle seed: seeded=%s ready=%s unavailable=%s missing=%s skipped=%s",
        stats["seeded"],
        stats["ready"],
        stats["unavailable"],
        stats["missing"],
        stats["skipped"],
    )
    return stats
