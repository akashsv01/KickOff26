"""Score manual brackets against finished match results."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Bracket, Match, MatchStatus


async def score_brackets(db: AsyncSession) -> int:
    """Update accuracy_score for all manual brackets based on finished matches."""
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.status == MatchStatus.FINISHED)
    )
    finished = {m.external_id or str(m.id): m for m in result.scalars().all()}

    brackets = await db.execute(select(Bracket).where(Bracket.mode == "manual"))
    updated = 0

    for bracket in brackets.scalars().all():
        picks = bracket.picks or {}
        if not picks:
            continue
        correct = 0
        total = 0
        for key, picked_team_id in picks.items():
            if key == "final":
                continue
            total += 1
            # Simple scoring: check if picked team won a known finished match
            for m in finished.values():
                if m.home_score is None or m.away_score is None:
                    continue
                if m.home_score > m.away_score and picked_team_id == m.home_team_id:
                    correct += 1
                    break
                if m.away_score > m.home_score and picked_team_id == m.away_team_id:
                    correct += 1
                    break

        if total > 0:
            bracket.accuracy_score = round(correct / total * 100, 2)
            updated += 1

    await db.flush()
    return updated
