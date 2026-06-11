"""Clear demo/fabricated live state when LIVE_DATA_MODE=api."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, MatchEvent, MatchStatus
from app.services.fixtures_loader import opening_match_external_id

logger = logging.getLogger(__name__)


async def _delete_match_events(db: AsyncSession, match_id: int) -> None:
    await db.execute(delete(MatchEvent).where(MatchEvent.match_id == match_id))


def _clear_live_scores(match: Match) -> None:
    match.status = MatchStatus.SCHEDULED
    match.home_score = None
    match.away_score = None
    match.minute = None
    match.win_prob_home = None
    match.win_prob_draw = None
    match.win_prob_away = None


async def reset_demo_fabrication_for_api_mode(db: AsyncSession) -> dict:
    """Remove stale demo LIVE matches and fabricated timelines before real API sync."""
    live_reset = 0
    result = await db.execute(select(Match).where(Match.status == MatchStatus.LIVE))
    for match in result.scalars().all():
        await _delete_match_events(db, match.id)
        _clear_live_scores(match)
        live_reset += 1

    opening_cleared = 0
    opening = (
        await db.execute(select(Match).where(Match.external_id == opening_match_external_id()))
    ).scalar_one_or_none()
    if opening:
        await _delete_match_events(db, opening.id)
        opening_cleared = 1
        if opening.status == MatchStatus.LIVE:
            _clear_live_scores(opening)
            live_reset += 1
        elif opening.status == MatchStatus.SCHEDULED and (
            opening.home_score is not None
            or opening.away_score is not None
            or opening.minute is not None
        ):
            opening.home_score = None
            opening.away_score = None
            opening.minute = None
            opening.win_prob_home = None
            opening.win_prob_draw = None
            opening.win_prob_away = None

    if live_reset or opening_cleared:
        logger.info(
            "Cleared demo fabrication for api mode: live_matches_reset=%s opening_timeline_cleared=%s",
            live_reset,
            opening_cleared,
        )
    return {"live_matches_reset": live_reset, "opening_timeline_cleared": opening_cleared}
