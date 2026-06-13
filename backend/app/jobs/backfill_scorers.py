"""One-time backfill: re-derive clean scorer timelines for past/live matches.

This corrects garbage written by the old parser (phantom "0' Unknown player",
braces/quotes, non-English names, duplicates, count mismatches) across the
existing database. Future matches are already handled by the hardened poller;
this is purely retroactive cleanup.

It reuses the SAME hardened logic as the live path - ``parse_scorers`` (validate +
count-match + English-only) and ``replace_side_goals`` (replace-the-set-per-side).
No second parser.

Behavior
  - Scans matches with status live or finished.
  - Re-fetches the authoritative payload from the live API (one ``/get/games``
    call) and matches it by ``api_object_id``. If a match has no api id or the
    feed no longer serves it, the match is skipped and logged (we never stored
    the raw strings to fall back on).
  - Per side: ``parse_scorers(raw, expected_count=api_side_score)``.
      * trustworthy (English, count == score) -> replace that side's goals.
      * None (malformed / non-English / count mismatch / "null") -> leave the
        side's stored goals untouched and flag for manual review.
  - Finished matches whose both sides parse cleanly are marked
    ``scorers_reconciled`` so the live path will not re-touch them.
  - Each match runs in its own savepoint, so one bad match cannot corrupt the
    rest. Any error degrades to "skip + log" and continues.

Safety
  - Dry-run by default: prints the before -> after per changed match and writes
    nothing. Pass ``--apply`` to persist.
  - Idempotent: re-running yields the same clean result (replace-set-per-side).
  - Uses the existing ``DATABASE_URL`` - run against local first, then point
    ``DATABASE_URL`` at Neon and run again to keep both identical.

Usage (from backend/)
    python -m app.jobs.backfill_scorers                # dry-run against $DATABASE_URL
    python -m app.jobs.backfill_scorers --apply        # write changes
    # then, with DATABASE_URL set to the Neon connection string, repeat.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database_url import database_url_label
from app.db import async_session, engine
from app.models import Match, MatchEvent, MatchStatus
from app.services.match_events import replace_side_goals
from app.services.worldcup_api import WorldCupApiClient, close_shared_http_client
from app.services.worldcup_parse import _first, api_object_id, parse_int, parse_scorers

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_scorers")


def _fmt_goal(row_or_dict) -> str:
    if isinstance(row_or_dict, dict):
        name = row_or_dict.get("player_name") or "(no name)"
        minute = row_or_dict.get("minute")
        added = row_or_dict.get("added_time")
    else:
        name = row_or_dict.player_name or "(no name)"
        minute = row_or_dict.minute
        added = row_or_dict.added_time
    if minute is None:
        stamp = "--'"
    else:
        stamp = f"{minute}+{added}'" if isinstance(added, int) and added > 0 else f"{minute}'"
    return f"{stamp} {name}"


def _fmt_side(goals) -> str:
    return "[" + ", ".join(_fmt_goal(g) for g in goals) + "]" if goals else "[]"


async def _stored_goals(db: AsyncSession, match_id: int, side: str) -> list[MatchEvent]:
    return list(
        (
            await db.execute(
                select(MatchEvent)
                .where(
                    MatchEvent.match_id == match_id,
                    MatchEvent.event_type == "goal",
                    MatchEvent.team_side == side,
                )
                .order_by(MatchEvent.minute, MatchEvent.id)
            )
        ).scalars().all()
    )


async def _require_schema() -> None:
    """Fail loudly if the structured-scorer columns are missing (schema drift)."""

    def _check(sync_conn) -> list[str]:
        insp = inspect(sync_conn)
        missing: list[str] = []
        me_cols = {c["name"] for c in insp.get_columns("match_events")}
        if "added_time" not in me_cols:
            missing.append("match_events.added_time")
        m_cols = {c["name"] for c in insp.get_columns("matches")}
        if "scorers_reconciled" not in m_cols:
            missing.append("matches.scorers_reconciled")
        return missing

    async with engine.connect() as conn:
        missing = await conn.run_sync(_check)
    if missing:
        raise SystemExit(
            "Schema drift - missing columns: "
            + ", ".join(missing)
            + ". Run `python -m app.setup` against this DATABASE_URL first."
        )


async def backfill(apply: bool) -> int:
    print(f"Database: {database_url_label(settings.database_url)}")
    print(f"Mode: {'APPLY (writing)' if apply else 'DRY-RUN (no writes)'}")

    client = WorldCupApiClient()
    if not client.configured:
        raise SystemExit(
            "No WORLDCUP_API_TOKEN configured - cannot re-fetch authoritative payloads."
        )

    # Fail fast on schema drift before making any network call.
    await _require_schema()

    scanned = cleaned = sides_replaced = entries_dropped = skipped = flagged = 0

    try:
        games = await client.get_games()
    finally:
        await close_shared_http_client()

    games_by_oid: dict[str, dict] = {}
    for g in games or []:
        if isinstance(g, dict):
            oid = api_object_id(g)
            if oid:
                games_by_oid[oid] = g
    print(f"Fetched {len(games_by_oid)} games from the live API.")

    async with async_session() as db:
        matches = (
            await db.execute(
                select(Match)
                .options(selectinload(Match.home_team), selectinload(Match.away_team))
                .where(Match.status.in_([MatchStatus.LIVE, MatchStatus.FINISHED]))
                .order_by(Match.id)
            )
        ).scalars().all()
        print(f"Scanning {len(matches)} live/finished matches.\n")

        for match in matches:
            scanned += 1
            label = f"match {match.id} {match.home_team.code}-{match.away_team.code}"
            game = games_by_oid.get(match.api_object_id or "")
            if game is None:
                skipped += 1
                logger.warning("SKIP %s: no authoritative payload (api_object_id=%s)",
                               label, match.api_object_id)
                continue

            api_home = parse_int(_first(game, "home_score", "homeScore", "score_home")) or 0
            api_away = parse_int(_first(game, "away_score", "awayScore", "score_away")) or 0
            home_raw = _first(game, "home_scorers", "homeScorers")
            away_raw = _first(game, "away_scorers", "awayScorers")
            home_parsed = parse_scorers(home_raw, api_home)
            away_parsed = parse_scorers(away_raw, api_away)

            match_changed = False
            try:
                for side, parsed, raw, score in (
                    ("home", home_parsed, home_raw, api_home),
                    ("away", away_parsed, away_raw, api_away),
                ):
                    before = await _stored_goals(db, match.id, side)
                    if parsed is None:
                        if score > 0 or before:
                            flagged += 1
                            logger.warning(
                                "FLAG %s %s: untrusted scorers, keeping %d stored. raw=%r",
                                label, side, len(before), raw,
                            )
                        continue
                    before_keys = {(g.player_name, g.minute, g.added_time) for g in before}
                    after_keys = {(p["player_name"], p["minute"], p["added_time"]) for p in parsed}
                    if before_keys == after_keys:
                        continue
                    print(
                        f"{label} {side}: {_fmt_side(before)} -> {_fmt_side(parsed)}"
                    )
                    sides_replaced += 1
                    match_changed = True
                    entries_dropped += max(0, len(before) - len(parsed))
                    if apply:
                        async with db.begin_nested():
                            await replace_side_goals(db, match.id, side, parsed)

                if apply:
                    # Keep the stored score authoritative for count consistency, and
                    # lock finished matches whose scorers fully reconciled.
                    async with db.begin_nested():
                        match.home_score = api_home
                        match.away_score = api_away
                        if (
                            match.status == MatchStatus.FINISHED
                            and home_parsed is not None
                            and away_parsed is not None
                        ):
                            match.scorers_reconciled = True
                    await db.commit()

                if match_changed:
                    cleaned += 1
            except Exception as exc:  # noqa: BLE001 - one bad match must not abort the run
                await db.rollback()
                skipped += 1
                logger.exception("ERROR %s: %s (rolled back, continuing)", label, exc)

    print("\n=== Summary ===")
    print(f"  matches scanned:        {scanned}")
    print(f"  matches cleaned:        {cleaned}")
    print(f"  sides replaced:         {sides_replaced}")
    print(f"  garbage entries dropped:{entries_dropped}")
    print(f"  flagged (kept as-is):   {flagged}")
    print(f"  skipped:                {skipped}")
    if not apply:
        print("\nDRY-RUN only - nothing was written. Re-run with --apply to persist.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without it the script is a dry-run (default).",
    )
    args = parser.parse_args(argv)
    return asyncio.run(backfill(apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
