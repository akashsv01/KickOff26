"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { TeamFlag } from "@/components/TeamFlag";
import { formatKickoff, matchDetailHref, navigateToMatchDetail, type Match } from "@/lib/matchday";
import { AnimatedScore } from "./AnimatedScore";
import { glassCardClass, matchCardClick, matchCardKeyDown } from "./GlassCard";
import { LiveBadge } from "./LiveBadge";
import { ProbBars } from "./ProbBars";

export function MatchCard({
  match: m,
  compact,
  hero,
  staggerIndex = 0,
}: {
  match: Match;
  compact?: boolean;
  hero?: boolean;
  staggerIndex?: number;
}) {
  const router = useRouter();
  const homeCode = m.home_team?.code ?? "???";
  const awayCode = m.away_team?.code ?? "???";
  const isLive = m.status === "live";
  const href = matchDetailHref(m.id);
  const goToDetail = () => navigateToMatchDetail(router.push, m.id);

  return (
    <Link
      href={href}
      data-testid="match-card-link"
      data-match-id={m.id}
      data-href={href}
      className="md-match-card-link block no-underline"
      onClick={(e) => matchCardClick(e, goToDetail)}
      onKeyDown={(e) => matchCardKeyDown(e, goToDetail)}
    >
      <div
        className={[
          glassCardClass(hero ? "live" : "default", true),
          hero ? "md-glass-hero p-6 sm:p-8" : "p-5",
          isLive && !hero ? "md-glass-live" : "",
          "md-animate-in",
        ]
          .filter(Boolean)
          .join(" ")}
        style={{ animationDelay: `${Math.min(staggerIndex, 12) * 45}ms` }}
      >
        <div className="md-glass-content">
          <div className="flex items-center justify-between">
            <span className="md-label">
              {m.city || "TBD"}
              {m.group_letter ? ` · Grp ${m.group_letter}` : ""}
            </span>
            {isLive ? (
              <LiveBadge minute={m.minute} />
            ) : (
              <span className="md-status-pill">{m.status.replace("_", " ")}</span>
            )}
          </div>
          {!compact && (
            <div className="mt-1.5 text-xs tabular-nums text-app-faint">
              {formatKickoff(m.kickoff_at)}
            </div>
          )}
          <div className="mt-4 flex items-center justify-between gap-2">
            <div className="min-w-0 flex-1 text-center">
              <div className="flex items-center justify-center gap-1.5">
                <TeamFlag code={homeCode} size="sm" />
                <span className="md-team-code tabular-nums">{homeCode}</span>
              </div>
              <div className="mt-1.5">
                <AnimatedScore value={m.home_score} large={hero} />
              </div>
            </div>
            <div className="shrink-0 text-center">
              {isLive && m.minute ? (
                <span className="md-match-clock">{m.minute}&apos;</span>
              ) : (
                <span className="text-sm font-semibold tracking-widest text-app-faint">VS</span>
              )}
            </div>
            <div className="min-w-0 flex-1 text-center">
              <div className="flex items-center justify-center gap-1.5">
                <span className="md-team-code tabular-nums">{awayCode}</span>
                <TeamFlag code={awayCode} size="sm" />
              </div>
              <div className="mt-1.5">
                <AnimatedScore value={m.away_score} large={hero} />
              </div>
            </div>
          </div>
          {m.win_prob_home != null && m.win_prob_draw != null && m.win_prob_away != null && (
            <div className="mt-5">
              <ProbBars
                home={m.win_prob_home}
                draw={m.win_prob_draw}
                away={m.win_prob_away}
                animate={isLive}
              />
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
