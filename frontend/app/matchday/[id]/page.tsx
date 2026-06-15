"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { FootballLoader } from "@/components/FootballLoader";
import { AnimatedScore } from "@/components/matchday/AnimatedScore";
import { LiveBadge } from "@/components/matchday/LiveBadge";
import { MatchTimeline } from "@/components/matchday/MatchTimeline";
import { ProbBars } from "@/components/matchday/ProbBars";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TeamFlag } from "@/components/TeamFlag";
import { formatKickoff, type Match } from "@/lib/matchday";
import { useDisplayTimezone } from "@/lib/timezone";
import { useWebSocket } from "@/lib/websocket";

export default function MatchDetailPage() {
  const params = useParams();
  const router = useRouter();
  const matchId = Number(params.id);
  const { user, token, refreshUser } = useAuth();
  const zone = useDisplayTimezone();
  const [match, setMatch] = useState<Match | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [followed, setFollowed] = useState<number[]>([]);
  const { connected, subscribe } = useWebSocket(token);

  const loadMatch = useCallback(async () => {
    try {
      const data = await api<Match>(`/matchday/matches/${matchId}`);
      setMatch(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Match not found");
    } finally {
      setLoading(false);
    }
  }, [matchId]);

  useEffect(() => {
    if (!Number.isFinite(matchId)) {
      setError("Invalid match");
      setLoading(false);
      return;
    }
    loadMatch();
  }, [matchId, loadMatch]);

  useEffect(() => {
    if (user) setFollowed(user.followed_team_ids || []);
  }, [user]);

  useEffect(() => {
    if (!connected || !match) return;
    const unsubs = [
      subscribe(`match:${match.id}`, (data) => {
        if (data.type === "match_update" && data.match) {
          setMatch(data.match as Match);
        }
      }),
      subscribe("matches:live", (data) => {
        if (data.type === "match_update" && data.match && (data.match as Match).id === matchId) {
          setMatch(data.match as Match);
        }
      }),
    ];
    return () => unsubs.forEach((u) => u());
  }, [connected, match?.id, matchId, subscribe]);

  async function followBoth() {
    if (!user || !match) {
      router.push("/auth");
      return;
    }
    const ids = new Set(followed);
    ids.add(match.home_team.id);
    ids.add(match.away_team.id);
    const list = Array.from(ids);
    await api("/teams/follow", { method: "POST", body: JSON.stringify({ team_ids: list }) });
    setFollowed(list);
    await refreshUser();
  }

  if (loading) {
    return (
      <div className="matchday-shell">
        <FootballLoader layout="section" label="Loading match…" />
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="matchday-shell">
        <div className="md-glass border-red-500/30 p-6">
          <p className="text-red-300">{error ?? "Match not found"}</p>
          <Link href="/matchday" className="md-btn md-btn-secondary mt-4 inline-flex">
            Back to Live Matches
          </Link>
        </div>
      </div>
    );
  }

  const isLive = match.status === "live";
  const isFinished = match.status === "finished";
  const ctx = match.model_context;
  const events = [...(match.events ?? [])].sort(
    (a, b) =>
      (a.minute ?? 9999) - (b.minute ?? 9999) || (a.added_time ?? 0) - (b.added_time ?? 0),
  );

  return (
    <div className="matchday-shell space-y-6">
      <Link
        href="/matchday"
        className="inline-flex text-sm text-champagne/90 transition hover:text-champagne"
      >
        ← Back to Live Matches
      </Link>

      <div className={`md-glass p-6 md-animate-in ${isLive ? "md-glass-live md-glass-hero" : ""}`}>
        <div className="md-glass-content">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-sm text-app-muted">
              <PinIcon className="h-4 w-4 shrink-0 text-champagne" />
              <span>
                {match.city}
                {match.venue ? `, ${match.venue}` : ""}
              </span>
            </span>
            {isLive ? (
              <LiveBadge minute={match.minute} />
            ) : (
              <span className="md-status-pill">{match.status.replace("_", " ")}</span>
            )}
          </div>
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs tabular-nums text-app-faint">
            <CalendarClockIcon className="h-4 w-4 shrink-0 text-champagne" />
            <span>
              {match.group_letter ? `Group ${match.group_letter} · ` : ""}
              {formatKickoff(match.kickoff_at, zone)}
            </span>
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-8">
            <TeamBlock team={match.home_team} score={match.home_score} />
            <span className="text-3xl font-light tracking-widest text-app-faint">-</span>
            <TeamBlock team={match.away_team} score={match.away_score} align="right" />
          </div>

          {match.win_prob_home != null && match.win_prob_draw != null && match.win_prob_away != null && (
            <div className="mx-auto mt-8 max-w-md">
              <h3 className="md-label mb-3 text-center">
                Win probability {isLive ? "(live)" : "(pre-match)"}
              </h3>
              <ProbBars
                home={match.win_prob_home}
                draw={match.win_prob_draw}
                away={match.win_prob_away}
                animate={isLive}
              />
              {isLive && ctx?.pre_match && (
                <p className="mt-3 text-center text-xs tabular-nums text-app-faint">
                  Pre-match baseline: H {(ctx.pre_match.home * 100).toFixed(0)}% · D{" "}
                  {(ctx.pre_match.draw * 100).toFixed(0)}% · A {(ctx.pre_match.away * 100).toFixed(0)}%
                </p>
              )}
            </div>
          )}

          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <button className="md-btn md-btn-secondary" onClick={followBoth}>
              Follow both teams
            </button>
            {!isFinished && (
              <Link href={`/watch?match=${match.id}`} className="md-btn md-btn-primary">
                Join Fan Room
              </Link>
            )}
          </div>
        </div>
      </div>

      {events.length > 0 && (
        <div className="md-glass p-6 md-animate-in" style={{ animationDelay: "60ms" }}>
          <div className="md-glass-content">
            <h2 className="md-section-title text-champagne">Match timeline</h2>
            <MatchTimeline match={match} events={events} isFinished={isFinished} />
            {isFinished && match.scorers_reconciled === false && (
              <p className="mt-4 text-xs text-app-faint">
                Some scorer details are unavailable for this match. The final score is correct -
                a few goalscorers were not provided by the data source.
              </p>
            )}
          </div>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <LineupCard
          title={match.home_team.name}
          code={match.home_team.code}
          lineup={match.home_lineup}
          formation={match.lineups?.home?.formation}
          delay={80}
        />
        <LineupCard
          title={match.away_team.name}
          code={match.away_team.code}
          lineup={match.away_lineup}
          formation={match.lineups?.away?.formation}
          delay={120}
        />
      </div>
    </div>
  );
}

function TeamBlock({
  team,
  score,
  align,
}: {
  team: Match["home_team"];
  score: number | null;
  align?: "right";
}) {
  return (
    <div className={`text-center ${align === "right" ? "md:text-right" : "md:text-left"}`}>
      <TeamFlag code={team.code} size="lg" className="mx-auto" />
      <div className="mt-3 md-team-code tabular-nums">{team.code}</div>
      <div className="mt-1 text-sm text-app-faint">{team.name}</div>
      <div className="mt-3">
        <AnimatedScore value={score} large />
      </div>
    </div>
  );
}

function LineupCard({
  title,
  code,
  lineup,
  formation,
  delay = 0,
}: {
  title: string;
  code: string;
  lineup?: { number: number; name: string; position: string }[];
  formation?: string | null;
  delay?: number;
}) {
  return (
    <div className="md-glass p-5 md-animate-in" style={{ animationDelay: `${delay}ms` }}>
      <div className="md-glass-content">
        <h3 className="flex items-center gap-2 font-semibold text-app">
          <TeamFlag code={code} size="sm" />
          <span>
            {title}
            {formation ? (
              <span className="ml-2 text-xs font-normal text-app-faint">{formation}</span>
            ) : null}
          </span>
        </h3>
        {lineup?.length ? (
          <ul className="mt-3 space-y-0 text-sm">
            {lineup.map((p) => (
              <li key={p.number} className="md-timeline-item flex justify-between py-1.5">
                <span>
                  <span className="tabular-nums text-app-faint">{p.number}</span> {p.name}
                </span>
                <span className="text-xs tracking-wide text-app-faint">{p.position}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-app-faint">Lineups not yet available.</p>
        )}
      </div>
    </div>
  );
}

function PinIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

function CalendarClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 7.5V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h6" />
      <path d="M16 2v4M8 2v4M3 10h18" />
      <circle cx="17.5" cy="16.5" r="4.5" />
      <path d="M17.5 14.8v1.7l1.2 1" />
    </svg>
  );
}
