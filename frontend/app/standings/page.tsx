"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FootballLoader } from "@/components/FootballLoader";
import { TeamFlag } from "@/components/TeamFlag";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { GroupStandings, StandingsResponse } from "@/lib/standings";
import { useWebSocket } from "@/lib/websocket";

function QualBadge({ q }: { q: "auto" | "third" | null }) {
  if (q === "auto") return <span className="standings-qual standings-qual-auto">Q</span>;
  if (q === "third") return <span className="standings-qual standings-qual-third">3rd</span>;
  return null;
}

function GroupTable({ group }: { group: GroupStandings }) {
  return (
    <section className={`standings-card md-glass${group.live ? " standings-card-live" : ""}`}>
      <div className="md-glass-content">
        <header className="standings-card-head">
          <h2 className="standings-group-title">Group {group.group}</h2>
          {group.live && (
            <span className="standings-live-pill">
              <span className="standings-live-dot" aria-hidden /> LIVE
            </span>
          )}
        </header>
        <div className="standings-table-wrap">
          <table className="standings-table">
            <thead>
              <tr>
                <th className="standings-th-pos">#</th>
                <th className="standings-th-team">Team</th>
                <th>P</th>
                <th>W</th>
                <th>D</th>
                <th>L</th>
                <th>GF</th>
                <th>GA</th>
                <th>GD</th>
                <th className="standings-th-pts">Pts</th>
              </tr>
            </thead>
            <tbody>
              {group.rows.map((row) => (
                <tr
                  key={row.code}
                  className={
                    row.qualification === "auto"
                      ? "standings-row-auto"
                      : row.qualification === "third"
                      ? "standings-row-third"
                      : ""
                  }
                >
                  <td className="standings-td-pos">{row.rank}</td>
                  <td className="standings-td-team">
                    <TeamFlag code={row.code} size="sm" />
                    <span className="standings-team-name">{row.name}</span>
                    <span className="standings-team-code">{row.code}</span>
                    <QualBadge q={row.qualification} />
                  </td>
                  <td>{row.played}</td>
                  <td>{row.won}</td>
                  <td>{row.drawn}</td>
                  <td>{row.lost}</td>
                  <td>{row.gf}</td>
                  <td>{row.ga}</td>
                  <td className="tabular-nums">{row.gd > 0 ? `+${row.gd}` : row.gd}</td>
                  <td className="standings-td-pts">{row.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default function StandingsPage() {
  const { token } = useAuth();
  const { connected, subscribe, reconnectCount } = useWebSocket(token);
  const [data, setData] = useState<StandingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api<StandingsResponse>("/matchday/standings");
      setData(res);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load standings");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!connected) return;
    load();
  }, [connected, reconnectCount, load]);

  // Live refresh: when a score changes anywhere, re-pull standings (debounced).
  useEffect(() => {
    if (!connected) return;
    return subscribe("matches:live", (msg) => {
      if (msg.type !== "match_update") return;
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      refreshTimer.current = setTimeout(load, 800);
    });
  }, [connected, subscribe, load]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="standings-header">
        <div>
          <h1 className="md-page-title">Standings</h1>
          <p className="standings-sub">
            Live group tables - top 2 of each group plus the 8 best third-placed teams advance to
            the Round of 32. Tiebreakers: points, goal difference, goals scored.
          </p>
        </div>
        <span className={connected ? "watch-live-indicator" : "watch-offline-indicator"}>
          <span className="watch-live-dot" aria-hidden />
          {connected ? "Live" : "Offline"}
        </span>
      </header>

      <div className="standings-legend">
        <span><span className="standings-swatch standings-swatch-auto" /> Group winner / runner-up</span>
        <span><span className="standings-swatch standings-swatch-third" /> Best third-placed</span>
      </div>

      {error && <p className="standings-error">{error}</p>}

      {!data && !error ? (
        <FootballLoader layout="section" label="Loading standings…" />
      ) : data && data.groups.length === 0 ? (
        <p className="standings-empty">Standings will populate once group fixtures begin.</p>
      ) : (
        <div className="standings-grid">
          {data?.groups.map((g) => (
            <GroupTable key={g.group} group={g} />
          ))}
        </div>
      )}
    </div>
  );
}
