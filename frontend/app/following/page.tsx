"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FootballLoader } from "@/components/FootballLoader";
import { FollowPicker } from "@/components/matchday/FollowPicker";
import { MatchCard } from "@/components/matchday/MatchCard";
import { TeamFlag } from "@/components/TeamFlag";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Match, Team } from "@/lib/matchday";
import { useWebSocket } from "@/lib/websocket";

export default function FollowingPage() {
  const { user, token, refreshUser } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [followed, setFollowed] = useState<number[]>([]);
  const [following, setFollowing] = useState<Match[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [followSaved, setFollowSaved] = useState<string | null>(null);
  const [savingFollow, setSavingFollow] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const followedTeams = useMemo(
    () => teams.filter((t) => followed.includes(t.id)),
    [teams, followed]
  );
  const followedCodes = useMemo(
    () => new Set(followedTeams.map((t) => t.code)),
    [followedTeams]
  );

  const applyMatchUpdate = useCallback((m: Match) => {
    setFollowing((prev) =>
      prev.map((x) =>
        x.id === m.id ? { ...x, ...m, local_date: m.local_date ?? x.local_date } : x
      )
    );
  }, []);

  const { connected, subscribe, reconnectCount } = useWebSocket(user ? token : null);

  const loadFollowing = useCallback(async () => {
    if (!user) {
      setFollowing([]);
      return;
    }
    try {
      const data = await api<Match[]>("/matchday/following");
      setFollowing(data);
    } catch {
      setFollowing([]);
    }
  }, [user]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api<Team[]>("/teams")
      .then(setTeams)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load teams"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!user) {
      setFollowing([]);
      setFollowed([]);
      return;
    }
    setFollowed(user.followed_team_ids || []);
    loadFollowing();
  }, [user, loadFollowing]);

  useEffect(() => {
    if (!connected || !user) return;
    loadFollowing();
  }, [connected, reconnectCount, user, loadFollowing]);

  useEffect(() => {
    if (!connected || followedCodes.size === 0) return;
    return subscribe("matches:live", (data) => {
      if (data.type !== "match_update" || !data.match) return;
      const m = data.match as Match;
      const home = m.home_team?.code;
      const away = m.away_team?.code;
      if (
        (home && followedCodes.has(home)) ||
        (away && followedCodes.has(away))
      ) {
        applyMatchUpdate(m);
      }
    });
  }, [connected, subscribe, applyMatchUpdate, followedCodes]);

  async function saveFollowed(ids: number[]) {
    if (!user) return;
    setSavingFollow(true);
    setFollowSaved(null);
    try {
      await api("/teams/follow", { method: "POST", body: JSON.stringify({ team_ids: ids }) });
      setFollowed(ids);
      setShowPicker(false);
      setFollowSaved(`Following ${ids.length} team${ids.length === 1 ? "" : "s"}`);
      await refreshUser();
      await loadFollowing();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save followed teams");
    } finally {
      setSavingFollow(false);
    }
  }

  function toggleFollow(id: number) {
    setFollowed((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function unfollowTeam(id: number) {
    const next = followed.filter((x) => x !== id);
    void saveFollowed(next);
  }

  if (loading) {
    return (
      <div className="matchday-shell">
        <FootballLoader layout="section" label="Loading your teams…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="matchday-shell">
        <div className="md-glass border-red-500/30 p-6 text-red-300">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="matchday-shell space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="md-page-title">Following</h1>
          <p className="mt-1 text-sm text-app-faint">
            Track your teams and their upcoming fixtures
          </p>
        </div>
        {user && (
          <button
            type="button"
            className="md-btn md-btn-secondary"
            onClick={() => {
              setShowPicker(!showPicker);
              setFollowSaved(null);
            }}
          >
            {showPicker ? "Hide team picker" : "Manage teams"}
          </button>
        )}
      </div>

      {!user ? (
        <div className="md-glass p-8 text-center">
          <p className="text-app-muted">
            <Link href="/auth" className="text-app-gold hover:underline">
              Log in
            </Link>{" "}
            to follow teams and see their next matches here.
          </p>
        </div>
      ) : (
        <>
          {followedTeams.length > 0 && (
            <section className="md-glass p-5">
              <div className="md-glass-content flex flex-wrap items-center justify-between gap-3">
                <h2 className="md-section-title">
                  Your teams
                  <span className="ml-2 text-sm font-normal tabular-nums text-app-faint">
                    ({followedTeams.length})
                  </span>
                </h2>
                {followSaved && (
                  <span className="text-sm font-medium text-green-400">{followSaved}</span>
                )}
              </div>
              <div className="md-glass-content mt-4 flex flex-wrap gap-2">
                {followedTeams.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => unfollowTeam(t.id)}
                    title={`Unfollow ${t.name}`}
                    className="md-team-chip md-team-chip-selected group"
                  >
                    <TeamFlag code={t.code} size="xs" />
                    {t.code}
                    <span className="ml-1 text-xs opacity-60 group-hover:opacity-100">×</span>
                  </button>
                ))}
              </div>
              <p className="md-glass-content mt-3 text-xs text-app-faint">
                Tap a team to unfollow. Use Manage teams to add more.
              </p>
            </section>
          )}

          {showPicker && (
            <FollowPicker
              teams={teams}
              followed={followed}
              onToggle={toggleFollow}
              onSave={() => saveFollowed(followed)}
              saving={savingFollow}
              savedMessage={followSaved}
            />
          )}

          <section>
            <h2 className="md-section-title mb-4">Upcoming matches</h2>
            {followed.length === 0 ? (
              <div className="md-glass p-8 text-center text-app-muted">
                <p>No teams followed yet.</p>
                <button
                  type="button"
                  className="md-btn md-btn-primary mt-4"
                  onClick={() => setShowPicker(true)}
                >
                  Pick teams to follow
                </button>
              </div>
            ) : following.length === 0 ? (
              <div className="md-glass p-8 text-center text-app-muted">
                No upcoming matches for your followed teams.
              </div>
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                {following.map((m, i) => (
                  <MatchCard key={`follow-${m.id}-${m.followed_team_id}`} match={m} staggerIndex={i} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
