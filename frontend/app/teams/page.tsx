"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FootballLoader } from "@/components/FootballLoader";
import { TeamFlag } from "@/components/TeamFlag";
import { PlayerToWatchCard } from "@/components/teams/PlayerToWatchCard";
import { TeamSquadBlock } from "@/components/teams/TeamSquad";
import { api } from "@/lib/api";
import { formatKickoff, type Match, type Team } from "@/lib/matchday";
import type { TeamProfile } from "@/lib/teams";

const GROUP_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"];

function teamMatches(matches: Match[], code: string): Match[] {
  return matches
    .filter((m) => m.home_team?.code === code || m.away_team?.code === code)
    .sort((a, b) => (a.kickoff_at ?? "").localeCompare(b.kickoff_at ?? ""));
}

function TeamDetail({
  team,
  matches,
  onBack,
}: {
  team: Team;
  matches: Match[];
  onBack: () => void;
}) {
  const [profile, setProfile] = useState<TeamProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      const data = await api<TeamProfile>(`/teams/${team.id}/profile`);
      setProfile(data);
      setProfileError(null);
      return data;
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to load squad");
      return null;
    }
  }, [team.id]);

  useEffect(() => {
    setProfile(null);
    setProfileError(null);
    void loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    if (profile?.squad.status !== "loading") return;
    const timer = window.setInterval(() => {
      void loadProfile();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [profile?.squad.status, loadProfile]);

  const fixtures = teamMatches(matches, team.code);
  const groupFixtures = fixtures.filter((m) => (m.stage ?? "group") === "group");
  const venues = Array.from(
    new Set(fixtures.map((m) => m.venue).filter(Boolean) as string[])
  );

  return (
    <div>
      <button type="button" className="md-btn-ghost team-detail-back" onClick={onBack}>
        ← All teams
      </button>

      <div className="team-detail-head">
        <TeamFlag code={team.code} size="lg" />
        <div>
          <h1 className="team-detail-title">{team.name}</h1>
          <p className="team-detail-sub">
            {team.group_letter ? `Group ${team.group_letter}` : "Group TBD"} · {team.code}
            {typeof team.elo_rating === "number" ? ` · Elo ${Math.round(team.elo_rating)}` : ""}
          </p>
        </div>
      </div>

      <h2 className="team-section-title">Group-stage fixtures</h2>
      {groupFixtures.length === 0 ? (
        <p className="teams-empty">No group fixtures available yet.</p>
      ) : (
        groupFixtures.map((m) => {
          const opp =
            m.home_team.code === team.code ? m.away_team : m.home_team;
          const score =
            m.home_score != null && m.away_score != null
              ? `${m.home_score}-${m.away_score}`
              : null;
          return (
            <div key={m.id} className="team-fixture">
              <span className="team-fixture-main">
                vs {opp.name} ({opp.code})
              </span>
              <span className="team-fixture-meta">
                {score ? `${score} · ` : ""}
                {m.status === "live" ? "LIVE · " : ""}
                {formatKickoff(m.kickoff_at)}
                {m.city ? ` · ${m.city}` : ""}
              </span>
            </div>
          );
        })
      )}

      {venues.length > 0 && (
        <>
          <h2 className="team-section-title">Venues</h2>
          <p className="team-fixture-meta">{venues.join(" · ")}</p>
        </>
      )}

      <h2 className="team-section-title">Coach</h2>
      {profile ? (
        <p className="team-coach-line">
          Coach: <span className="team-coach-name">{profile.coach_display}</span>
        </p>
      ) : profileError ? (
        <p className="teams-error">{profileError}</p>
      ) : (
        <FootballLoader size="sm" label="Loading coach…" />
      )}

      {profile?.player_to_watch && (
        <>
          <h2 className="team-section-title">Featured</h2>
          <PlayerToWatchCard entry={profile.player_to_watch} teamCode={team.code} />
        </>
      )}

      <h2 className="team-section-title">Squad</h2>
      {profile ? (
        <TeamSquadBlock profile={profile} />
      ) : profileError ? null : (
        <div className="squad-state">
          <FootballLoader size="sm" label="Loading squad…" />
        </div>
      )}
    </div>
  );
}

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Team | null>(null);

  useEffect(() => {
    Promise.all([api<Team[]>("/teams"), api<Match[]>("/matchday/matches")])
      .then(([t, m]) => {
        setTeams(t);
        setMatches(m);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load teams")
      );
  }, []);

  const grouped = useMemo(() => {
    const map: Record<string, Team[]> = {};
    for (const t of teams ?? []) {
      const g = t.group_letter ?? "?";
      (map[g] ??= []).push(t);
    }
    for (const g of Object.keys(map)) {
      map[g].sort((a, b) => a.name.localeCompare(b.name));
    }
    return map;
  }, [teams]);

  const orderedGroups = useMemo(() => {
    const keys = Object.keys(grouped);
    return [
      ...GROUP_ORDER.filter((g) => keys.includes(g)),
      ...keys.filter((g) => !GROUP_ORDER.includes(g)),
    ];
  }, [grouped]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {selected ? (
        <TeamDetail team={selected} matches={matches} onBack={() => setSelected(null)} />
      ) : (
        <>
          <header className="teams-header">
            <div>
              <h1 className="md-page-title">Teams &amp; Stats</h1>
              <p className="teams-sub">
                All 48 nations of the 2026 tournament, grouped A-L. Tap a team for its fixtures
                and venue context. Data is sourced from the live tournament feed.
              </p>
            </div>
          </header>

          {error && <p className="teams-error">{error}</p>}

          {!teams && !error ? (
            <FootballLoader layout="section" label="Loading teams…" />
          ) : (
            orderedGroups.map((g) => (
              <section key={g} className="teams-group">
                <h2 className="teams-group-title">Group {g}</h2>
                <div className="teams-grid">
                  {grouped[g].map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className="team-card"
                      onClick={() => setSelected(t)}
                    >
                      <TeamFlag code={t.code} size="lg" />
                      <div className="team-card-text">
                        <span className="team-card-name">{t.name}</span>
                        <span className="team-card-meta">
                          {t.code} · Group {t.group_letter ?? "?"}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            ))
          )}
        </>
      )}
    </div>
  );
}
