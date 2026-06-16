"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FootballLoader } from "@/components/FootballLoader";
import { MatchStatusBadge } from "@/components/matchday/MatchStatusBadge";
import { TeamFlag } from "@/components/TeamFlag";
import { api } from "@/lib/api";
import { formatKickoff, matchDetailHref } from "@/lib/matchday";
import { TimesInZoneLabel, useDisplayTimezone } from "@/lib/timezone";

type StadiumMatch = {
  id: number;
  home_team: { id: number; name: string; code: string };
  away_team: { id: number; name: string; code: string };
  home_score: number | null;
  away_score: number | null;
  minute: number | null;
  status: string;
  stage: string | null;
  group_letter: string | null;
  kickoff_at: string | null;
};

type StadiumDetail = {
  id: number;
  name: string;
  city: string | null;
  country: string | null;
  capacity: number | null;
  match_count: number;
  matches: StadiumMatch[];
};

const STAGE_ORDER = ["group", "r32", "r16", "qf", "sf", "third", "final"];
const STAGE_LABEL: Record<string, string> = {
  group: "Group stage",
  r32: "Round of 32",
  r16: "Round of 16",
  qf: "Quarter-finals",
  sf: "Semi-finals",
  third: "Third-place play-off",
  final: "Final",
};

function stageLabel(stage: string | null): string {
  if (!stage) return "Other";
  return STAGE_LABEL[stage] ?? stage;
}

function isPlayed(m: StadiumMatch): boolean {
  return m.status === "finished" || (m.status === "live" && m.home_score !== null);
}

function StadiumIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="stadium-hero-icon" aria-hidden>
      <path d="M3 9c0-1.7 4-3 9-3s9 1.3 9 3-4 3-9 3-9-1.3-9-3Z" />
      <path d="M3 9v6c0 1.7 4 3 9 3s9-1.3 9-3V9" />
      <path d="M9 12v6M15 12v6" />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

function SeatsIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13A4 4 0 0 1 16 11" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect width="18" height="18" x="3" y="4" rx="2" />
      <path d="M3 10h18M8 2v4M16 2v4" />
    </svg>
  );
}

export default function StadiumDetailPage() {
  const params = useParams();
  const stadiumId = Number(params.id);
  const zone = useDisplayTimezone();
  const [stadium, setStadium] = useState<StadiumDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!stadiumId) return;
    api<StadiumDetail>(`/stadiums/${stadiumId}`)
      .then(setStadium)
      .catch((e) => setError(e instanceof Error ? e.message : "Stadium not found"));
  }, [stadiumId]);

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="md-glass border-red-500/30 p-6 text-red-300">{error}</div>
      </div>
    );
  }

  if (!stadium) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <FootballLoader layout="section" label="Loading stadium…" />
      </div>
    );
  }

  // Group matches by stage in tournament order (chronological within each group).
  const groups = STAGE_ORDER.map((stage) => ({
    stage,
    label: stageLabel(stage),
    matches: stadium.matches.filter((m) => (m.stage ?? "group") === stage),
  })).filter((g) => g.matches.length > 0);
  // Any unexpected stage falls into a trailing "Other" group.
  const known = new Set(STAGE_ORDER);
  const other = stadium.matches.filter((m) => !known.has(m.stage ?? "group"));
  if (other.length) groups.push({ stage: "other", label: "Other", matches: other });

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Link href="/stadiums" className="text-sm text-app-muted hover:text-champagne">
        ← All stadiums
      </Link>

      <header className="stadium-hero">
        <div className="stadium-hero-title">
          <StadiumIcon />
          <h1 className="md-page-title">{stadium.name}</h1>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {(stadium.city || stadium.country) && (
            <span className="meta-chip">
              <PinIcon /> {[stadium.city, stadium.country].filter(Boolean).join(", ")}
            </span>
          )}
          {stadium.capacity ? (
            <span className="meta-chip">
              <SeatsIcon /> {stadium.capacity.toLocaleString()} seats
            </span>
          ) : null}
          <span className="meta-chip">
            <CalendarIcon /> {stadium.match_count} {stadium.match_count === 1 ? "match" : "matches"}
          </span>
        </div>
      </header>

      {groups.length === 0 ? (
        <p className="mt-6 text-app-faint">No matches are scheduled at this venue yet.</p>
      ) : (
        groups.map((group) => (
          <section key={group.stage} className="mt-6">
            <h2 className="resource-section-title">{group.label}</h2>
            <div className="md-glass">
              <div className="md-glass-content divide-y divide-white/8">
                {group.matches.map((m) => (
                  <Link key={m.id} href={matchDetailHref(m.id)} className="stadium-match-row">
                    <span className="stadium-match-time">{formatKickoff(m.kickoff_at, zone)}</span>
                    <span className="stadium-match-teams">
                      <span>{m.home_team.code}</span>
                      <TeamFlag code={m.home_team.code} size="sm" />
                      {isPlayed(m) ? (
                        <span className="stadium-match-score">
                          {m.home_score ?? 0} - {m.away_score ?? 0}
                        </span>
                      ) : (
                        <span className="stadium-match-vs">vs</span>
                      )}
                      <TeamFlag code={m.away_team.code} size="sm" />
                      <span>{m.away_team.code}</span>
                    </span>
                    <span className="stadium-match-right">
                      {m.group_letter ? <span className="stadium-grp-chip">Grp {m.group_letter}</span> : null}
                      <MatchStatusBadge status={m.status} minute={m.minute} />
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          </section>
        ))
      )}

      {stadium.matches.length > 0 && <TimesInZoneLabel className="mt-6 block text-xs text-app-faint" />}
    </div>
  );
}
