"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { TeamFlag } from "@/components/TeamFlag";
import { AnimatedScore } from "@/components/matchday/AnimatedScore";
import { LiveBadge } from "@/components/matchday/LiveBadge";
import { formatKickoff, matchDetailHref, type Match } from "@/lib/matchday";
import { OFFICIAL_TOURNAMENT_LINKS, matchHeaderLine, type WatchParticipant } from "@/lib/watch";
import { WatchPresenceStrip } from "./WatchPresence";

type Props = {
  match: Match;
  watcherCount: number;
  participants: WatchParticipant[];
  connected: boolean;
};

export function WatchRoomHeader({ match, watcherCount, participants, connected }: Props) {
  const home = match.home_team;
  const away = match.away_team;
  const isLive = match.status === "live";
  const isFinished = match.status === "finished";
  const prevScore = useRef(`${match.home_score}-${match.away_score}`);
  const [scorePulse, setScorePulse] = useState(false);

  useEffect(() => {
    const key = `${match.home_score}-${match.away_score}`;
    if (prevScore.current !== key && match.home_score != null) {
      setScorePulse(true);
      const t = window.setTimeout(() => setScorePulse(false), 700);
      prevScore.current = key;
      return () => window.clearTimeout(t);
    }
    prevScore.current = key;
  }, [match.home_score, match.away_score]);

  return (
    <header
      className={[
        "watch-match-hero",
        isLive ? "watch-match-hero-live" : "",
        isFinished ? "watch-match-hero-finished" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label={`${home?.code} vs ${away?.code} watch room`}
    >
      <div className="watch-match-hero-glow" aria-hidden />

      <div className="watch-match-hero-top">
        <div className="watch-match-hero-brand">
          <p className="watch-room-eyebrow">Fan Rooms</p>
          <WatchPresenceStrip count={watcherCount} participants={participants} />
        </div>
        <span className={connected ? "watch-live-indicator" : "watch-offline-indicator"}>
          <span className="watch-live-dot" aria-hidden />
          {connected ? "Connected" : "Reconnecting…"}
        </span>
      </div>

      <div className="watch-match-hero-scoreboard">
        <div className="watch-match-hero-side">
          <TeamFlag code={home?.code ?? "???"} size="lg" className="watch-hero-flag" />
          <span className="watch-match-hero-code">{home?.code}</span>
          <span className="watch-match-hero-name">{home?.name ?? home?.code}</span>
        </div>

        <div className="watch-match-hero-center">
          {isLive ? (
            <span className="watch-hero-live-badge">
              <LiveBadge minute={match.minute} />
            </span>
          ) : isFinished ? (
            <span className="watch-header-badge watch-header-badge-final">Final</span>
          ) : (
            <span className="watch-header-badge watch-header-badge-upcoming">Upcoming</span>
          )}

          <div className={`watch-hero-score-row${scorePulse ? " watch-hero-score-pulse" : ""}`}>
            <AnimatedScore value={match.home_score} large />
            <span className="watch-hero-score-sep">-</span>
            <AnimatedScore value={match.away_score} large />
          </div>

          {!isLive && !isFinished && (
            <p className="watch-match-hero-kickoff">{formatKickoff(match.kickoff_at)}</p>
          )}
          {isLive && match.minute != null && (
            <p className="watch-match-hero-clock">{match.minute}&apos;</p>
          )}
        </div>

        <div className="watch-match-hero-side watch-match-hero-side-away">
          <TeamFlag code={away?.code ?? "???"} size="lg" className="watch-hero-flag" />
          <span className="watch-match-hero-code">{away?.code}</span>
          <span className="watch-match-hero-name">{away?.name ?? away?.code}</span>
        </div>
      </div>

      <p className="watch-match-hero-meta">{matchHeaderLine(match)}</p>

      <div className="watch-match-hero-actions">
        <Link href={matchDetailHref(match.id)} className="watch-pill-btn watch-pill-btn-secondary">
          Match detail
        </Link>
        <a
          href={OFFICIAL_TOURNAMENT_LINKS.tournament}
          target="_blank"
          rel="noopener noreferrer"
          className="watch-pill-btn watch-pill-btn-primary"
        >
          Where to watch
        </a>
        <a
          href={OFFICIAL_TOURNAMENT_LINKS.broadcasters}
          target="_blank"
          rel="noopener noreferrer"
          className="watch-broadcast-note"
          title="Official broadcast information - not a stream link"
        >
          Find your local broadcaster
        </a>
      </div>
    </header>
  );
}
