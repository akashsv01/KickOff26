"use client";

import { useMemo, useState } from "react";
import { DateStrip } from "@/components/matchday/DateStrip";
import { TournamentCalendar } from "@/components/matchday/TournamentCalendar";
import {
  dayCountsFromMatches,
  defaultMatchDay,
  localTodayKey,
  formatDayLabel,
  type Match,
} from "@/lib/matchday";
import {
  filterMatchesByDay,
  filterMatchesBySearch,
  liveMatchesAll,
  sortBrowseMatches,
  upNextTodayMatches,
  type RoomSummary,
} from "@/lib/watch";
import { useDisplayTimezone } from "@/lib/timezone";
import { WatchRoomCard } from "./WatchRoomCard";

type Props = {
  matches: Match[];
  summaries: Map<number, RoomSummary>;
  activeRoomId: number | null;
  onJoin: (matchId: number) => void;
};

export function WatchRoomBrowser({ matches, summaries, activeRoomId, onJoin }: Props) {
  const zone = useDisplayTimezone();
  const today = localTodayKey(zone);
  const days = useMemo(() => dayCountsFromMatches(matches, zone), [matches, zone]);
  const [selectedDay, setSelectedDay] = useState(() => defaultMatchDay(days.map((d) => d.date), zone));
  const [search, setSearch] = useState("");
  const [showCalendar, setShowCalendar] = useState(false);

  const liveAll = useMemo(() => sortBrowseMatches(liveMatchesAll(matches), summaries), [matches, summaries]);
  const upNext = useMemo(
    () => sortBrowseMatches(upNextTodayMatches(matches, today, zone), summaries),
    [matches, summaries, today, zone]
  );

  const browsePool = useMemo(() => {
    let pool = filterMatchesByDay(matches, selectedDay, zone);
    pool = filterMatchesBySearch(pool, search);
    return sortBrowseMatches(pool, summaries);
  }, [matches, selectedDay, search, summaries, zone]);

  return (
    <aside id="watch-room-browser" className="watch-browser md-glass" aria-label="Room browser">
      <div className="md-glass-content watch-browser-inner">
        <div className="watch-browser-head">
          <h2 className="md-section-title">Find a room</h2>
          <p className="watch-browser-sub">Join fans watching live - rooms sorted by activity.</p>
        </div>

        {liveAll.length > 0 ? (
          <section className="watch-browser-section">
            <h3 className="watch-section-label watch-section-live">Live now</h3>
            <div className="watch-room-card-stack">
              {liveAll.map((m) => (
                <WatchRoomCard
                  key={m.id}
                  match={m}
                  summaries={summaries}
                  activeRoomId={activeRoomId}
                  onJoin={onJoin}
                  hero
                />
              ))}
            </div>
          </section>
        ) : (
          <div className="watch-empty-live">
            <p>No live matches right now</p>
            <p className="watch-empty-live-sub">Here&apos;s what&apos;s coming up today.</p>
          </div>
        )}

        {upNext.length > 0 && (
          <section className="watch-browser-section">
            <h3 className="watch-section-label">Up next · today</h3>
            <div className="watch-room-card-stack">
              {upNext.slice(0, 6).map((m) => (
                <WatchRoomCard
                  key={m.id}
                  match={m}
                  summaries={summaries}
                  activeRoomId={activeRoomId}
                  onJoin={onJoin}
                />
              ))}
            </div>
          </section>
        )}

        <section className="watch-browser-section">
          <div className="watch-browse-toolbar">
            <h3 className="watch-section-label">Browse matches</h3>
            <button
              type="button"
              className="md-btn md-btn-ghost watch-calendar-toggle"
              onClick={() => setShowCalendar((v) => !v)}
            >
              {showCalendar ? "Hide calendar" : "Calendar"}
            </button>
          </div>

          <input
            type="search"
            className="watch-search"
            placeholder="Search team or city…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search matches"
          />

          {showCalendar ? (
            <TournamentCalendar
              days={days}
              selected={selectedDay}
              onSelect={setSelectedDay}
              zone={zone}
              className="watch-calendar"
            />
          ) : (
            <DateStrip days={days} selected={selectedDay} onSelect={setSelectedDay} />
          )}

          <p className="watch-day-caption">{selectedDay ? formatDayLabel(selectedDay) : "All days"}</p>

          <div className="watch-room-card-stack watch-room-card-stack-compact">
            {browsePool.length === 0 ? (
              <p className="watch-browse-empty">No matches for this day{search ? " matching your search" : ""}.</p>
            ) : (
              browsePool.map((m) => (
                <WatchRoomCard
                  key={m.id}
                  match={m}
                  summaries={summaries}
                  activeRoomId={activeRoomId}
                  onJoin={onJoin}
                />
              ))
            )}
          </div>
        </section>
      </div>
    </aside>
  );
}
