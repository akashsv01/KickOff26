"use client";

import { TeamFlag } from "@/components/TeamFlag";
import { AnimatedScore } from "@/components/matchday/AnimatedScore";
import { LiveBadge } from "@/components/matchday/LiveBadge";
import { formatKickoff, type Match } from "@/lib/matchday";
import { useDisplayTimezone } from "@/lib/timezone";
import { matchStatusLabel, watcherCountForMatch, type RoomSummary } from "@/lib/watch";

type Props = {
  match: Match;
  summaries: Map<number, RoomSummary>;
  activeRoomId: number | null;
  onJoin: (matchId: number) => void;
  hero?: boolean;
};

export function WatchRoomCard({ match, summaries, activeRoomId, onJoin, hero }: Props) {
  const zone = useDisplayTimezone();
  const home = match.home_team?.code ?? "???";
  const away = match.away_team?.code ?? "???";
  const isLive = match.status === "live";
  const status = matchStatusLabel(match.status);
  const watching = watcherCountForMatch(match.id, summaries);
  const roomId = summaries.get(match.id)?.room_id ?? null;
  const isActive = roomId != null && roomId === activeRoomId;

  return (
    <button
      type="button"
      className={[
        "watch-room-card",
        hero ? "watch-room-card-hero" : "",
        isActive ? "watch-room-card-active" : "",
        isLive ? "watch-room-card-live" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={() => onJoin(match.id)}
    >
      <div className="watch-room-card-top">
        <span className="watch-room-card-venue">
          {match.city || "TBD"}
          {match.group_letter ? ` · Grp ${match.group_letter}` : ""}
        </span>
        {isLive ? (
          <LiveBadge minute={match.minute} />
        ) : (
          <span className={`watch-status-pill watch-status-${status.toLowerCase()}`}>{status}</span>
        )}
      </div>

      <div className="watch-room-card-teams">
        <div className="watch-room-card-team">
          <TeamFlag code={home} size="sm" />
          <span className="watch-team-code">{home}</span>
          {isLive || match.status === "finished" ? (
            <AnimatedScore value={match.home_score} />
          ) : null}
        </div>
        <span className="watch-room-card-vs">{isLive && match.minute ? `${match.minute}'` : "vs"}</span>
        <div className="watch-room-card-team">
          <TeamFlag code={away} size="sm" />
          <span className="watch-team-code">{away}</span>
          {isLive || match.status === "finished" ? (
            <AnimatedScore value={match.away_score} />
          ) : null}
        </div>
      </div>

      <div className="watch-room-card-meta">
        <span>{isLive ? "In progress" : formatKickoff(match.kickoff_at, zone)}</span>
        <span className="watch-watching-count">
          <span className="watch-watching-dot" aria-hidden />
          {watching} watching
        </span>
      </div>
    </button>
  );
}
