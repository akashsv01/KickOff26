"use client";

import { PlayerAvatar } from "@/components/teams/PlayerAvatar";
import type { PlayerToWatch } from "@/lib/teams";

export function PlayerToWatchCard({
  entry,
  teamCode,
}: {
  entry: PlayerToWatch;
  teamCode: string;
}) {
  return (
    <article className="ptw-card md-glass">
      <p className="ptw-kicker">Player to Watch</p>
      <div className="ptw-body">
        <PlayerAvatar name={entry.player} teamCode={teamCode} imageUrl={entry.image_url} size="lg" />
        <div className="ptw-copy">
          <h3 className="ptw-name">{entry.player}</h3>
          <p className="ptw-reason">{entry.reason}</p>
        </div>
      </div>
    </article>
  );
}
