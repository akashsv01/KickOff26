"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DateStrip } from "@/components/matchday/DateStrip";
import { MatchCard } from "@/components/matchday/MatchCard";
import { MatchDaySummaryPanel } from "@/components/matchday/MatchDaySummaryPanel";
import { NotificationsPanel } from "@/components/matchday/NotificationBell";
import { ToastStack, type Toast } from "@/components/matchday/ToastStack";
import { FootballLoader } from "@/components/FootballLoader";
import { TournamentCalendar } from "@/components/matchday/TournamentCalendar";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  dayCountsFromMatches,
  defaultMatchDay,
  formatDayLabel,
  groupByKickoffSlot,
  matchesForDay,
  shouldShowAlert,
  sortDayMatches,
  type Match,
  type MatchAlertPayload,
} from "@/lib/matchday";
import { useMatchDayNotifications } from "@/lib/matchday-notifications";
import { TimesInZoneLabel, useDisplayTimezone } from "@/lib/timezone";
import { useWebSocket } from "@/lib/websocket";

export default function MatchDayPage() {
  const { token } = useAuth();
  const zone = useDisplayTimezone();
  const { addStatusNotification } = useMatchDayNotifications();
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedDay, setSelectedDay] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const statusByMatchId = useRef<Map<number, string>>(new Map());
  const { connected, subscribe, reconnectCount } = useWebSocket(token);

  const liveCount = useMemo(() => matches.filter((m) => m.status === "live").length, [matches]);
  // Day badges bucket by the SAME active zone used to display kickoff times.
  const days = useMemo(() => dayCountsFromMatches(matches, zone), [matches, zone]);

  const dayMatches = useMemo(() => {
    if (!selectedDay) return [];
    return sortDayMatches(matchesForDay(matches, selectedDay, zone));
  }, [matches, selectedDay, zone]);

  const liveMatches = useMemo(
    () => dayMatches.filter((m) => m.status === "live"),
    [dayMatches]
  );

  const scheduledMatches = useMemo(
    () => dayMatches.filter((m) => m.status !== "live"),
    [dayMatches]
  );

  const slotGroups = useMemo(
    () => groupByKickoffSlot(scheduledMatches, zone),
    [scheduledMatches, zone]
  );

  const primaryLiveMatch = liveMatches[0] ?? matches.find((m) => m.status === "live") ?? null;

  const pushToast = useCallback((message: string, type: Toast["type"]) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev.slice(-4), { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 6000);
  }, []);

  const trackStatusChange = useCallback(
    (m: Match) => {
      const prev = statusByMatchId.current.get(m.id);
      const home = m.home_team?.code ?? "Home";
      const away = m.away_team?.code ?? "Away";

      if (prev && prev !== "live" && m.status === "live") {
        addStatusNotification(
          "match_start",
          m.id,
          `KICK OFF: ${home} vs ${away}`
        );
        pushToast(`KICK OFF: ${home} vs ${away}`, "momentum");
      }
      if (prev === "live" && m.status === "finished") {
        addStatusNotification(
          "match_end",
          m.id,
          `FULL TIME: ${home} ${m.home_score ?? 0}-${m.away_score ?? 0} ${away}`
        );
        pushToast(`FULL TIME: ${home} vs ${away}`, "momentum");
      }
      statusByMatchId.current.set(m.id, m.status);
    },
    [addStatusNotification, pushToast]
  );

  const applyMatchUpdate = useCallback(
    (m: Match) => {
      trackStatusChange(m);
      setMatches((prev) =>
        prev.map((x) =>
          x.id === m.id ? { ...x, ...m, local_date: m.local_date ?? x.local_date } : x
        )
      );
      setLastUpdated(new Date());
    },
    [trackStatusChange]
  );

  useEffect(() => {
    setLoading(true);
    setError(null);
    api<Match[]>("/matchday/matches")
      .then((m) => {
        setMatches(m);
        for (const match of m) {
          statusByMatchId.current.set(match.id, match.status);
        }
        const dateKeys = dayCountsFromMatches(m, zone).map((x) => x.date);
        setSelectedDay(defaultMatchDay(dateKeys, zone));
        setLastUpdated(new Date());
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load matches"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!connected) return;
    api<Match[]>("/matchday/matches")
      .then((m) => {
        setMatches(m);
        for (const match of m) {
          statusByMatchId.current.set(match.id, match.status);
        }
        setLastUpdated(new Date());
      })
      .catch(() => {
        /* keep last-known state on resync failure */
      });
  }, [connected, reconnectCount]);

  useEffect(() => {
    if (!connected) return;

    const unsubs = [
      subscribe("matches:live", (data) => {
        if (data.type === "match_update" && data.match) {
          applyMatchUpdate(data.match as Match);
        }
      }),
      subscribe("matches:alerts", (data) => {
        const alert = data as MatchAlertPayload;
        if (!shouldShowAlert(alert)) return;
        // Notifications are collected app-wide by MatchDayNotificationsProvider;
        // here we only surface transient toasts.
        const msg = String(alert.message ?? "");
        if (!msg) return;
        if (alert.type === "goal_alert") pushToast(msg, "goal");
        else if (
          alert.type === "red_card_alert" ||
          alert.type === "yellow_card_alert"
        )
          pushToast(msg, "card");
        else if (alert.type === "momentum_alert") pushToast(msg, "momentum");
        else pushToast(msg, "momentum");
      }),
    ];

    matches.forEach((m) => {
      if (m.status === "live") {
        unsubs.push(
          subscribe(`match:${m.id}`, (data) => {
            if (data.type === "match_update" && data.match) {
              applyMatchUpdate(data.match as Match);
            }
          })
        );
      }
    });

    return () => unsubs.forEach((u) => u());
  }, [connected, matches, subscribe, applyMatchUpdate, pushToast]);

  if (loading) {
    return (
      <div className="matchday-shell">
        <FootballLoader layout="section" label="Loading fixtures…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="matchday-shell">
        <div className="md-glass border-red-500/30 p-6 text-red-300">
          <h1 className="text-xl font-bold">Live Matches unavailable</h1>
          <p className="mt-2 text-sm">{error}</p>
          <button className="md-btn md-btn-secondary mt-4" onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="matchday-shell">
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((p) => p.filter((t) => t.id !== id))} />

      <div className="md-matchday-grid">
        <aside className="md-matchday-sidebar">
          {days.length > 0 && (
            <>
              <DateStrip days={days} selected={selectedDay} onSelect={setSelectedDay} />
              <TournamentCalendar
                days={days}
                selected={selectedDay}
                onSelect={setSelectedDay}
                zone={zone}
                className="hidden lg:block"
              />
            </>
          )}
          <MatchDaySummaryPanel liveCount={liveCount} liveMatch={primaryLiveMatch} zone={zone} />
          <NotificationsPanel />
        </aside>

        <div className="md-matchday-main">
          <header className="md-day-header">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h1 className="md-day-header-title">
                  Live Matches
                  {selectedDay ? ` - ${formatDayLabel(selectedDay)}` : ""}
                </h1>
                <p className="md-day-header-date tabular-nums">
                  {matches.length} fixtures
                  {lastUpdated ? ` · Updated ${lastUpdated.toLocaleTimeString()}` : ""}
                </p>
              </div>
              {liveCount > 0 && (
                <span className="md-live-indicator text-sm">
                  <span className="md-live-indicator-dot" aria-hidden />
                  {liveCount} live
                </span>
              )}
            </div>
          </header>

          {dayMatches.length === 0 ? (
            <div className="md-glass p-8 text-center text-app-faint">
              <div className="md-glass-content">No fixtures on this date.</div>
            </div>
          ) : (
            <div key={selectedDay}>
              {liveMatches.length > 0 && (
                <div className="md-live-hero-anchor space-y-4">
                  {liveMatches.map((m, i) => (
                    <MatchCard key={m.id} match={m} hero staggerIndex={i} />
                  ))}
                </div>
              )}

              {scheduledMatches.length > 0 && (
                <div className="space-y-6">
                  {Object.entries(slotGroups).map(([slot, list]) => (
                    <div key={slot}>
                      <h3 className="md-label mb-3">{slot}</h3>
                      <div className="grid gap-4 sm:grid-cols-2">
                        {list.map((m, i) => (
                          <MatchCard
                            key={m.id}
                            match={m}
                            staggerIndex={liveMatches.length + i}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {dayMatches.length > 0 && (
            <TimesInZoneLabel className="fixed bottom-3 left-4 z-40 rounded-md bg-black/45 px-3 py-1.5 text-xs font-bold text-app-secondary shadow-lg backdrop-blur" />
          )}
        </div>
      </div>
    </div>
  );
}
