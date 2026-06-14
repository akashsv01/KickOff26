"use client";

import { localTodayKey } from "@/lib/matchday";
import { useMemo, useState } from "react";

const MONTHS = ["June 2026", "July 2026"] as const;

function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function pad(n: number) {
  return String(n).padStart(2, "0");
}

export function TournamentCalendar({
  days,
  selected,
  onSelect,
  zone,
  windowStart = "2026-06-11",
  windowEnd = "2026-07-19",
  className = "",
}: {
  days: { date: string; match_count: number }[];
  selected: string;
  onSelect: (date: string) => void;
  zone?: string | null;
  windowStart?: string;
  windowEnd?: string;
  className?: string;
}) {
  const [monthIdx, setMonthIdx] = useState(0);
  const counts = useMemo(() => Object.fromEntries(days.map((d) => [d.date, d.match_count])), [days]);
  // "Today" highlight uses the same active zone as the day badges (passed in).
  const today = localTodayKey(zone);

  const year = 2026;
  const month = monthIdx;
  const monthNum = month + 6;
  const totalDays = daysInMonth(year, month);
  const firstDow = new Date(year, month, 1).getDay();

  const cells: (string | null)[] = [
    ...Array(firstDow).fill(null),
    ...Array.from({ length: totalDays }, (_, i) => `${year}-${pad(monthNum)}-${pad(i + 1)}`),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  function inWindow(dateKey: string) {
    return dateKey >= windowStart && dateKey <= windowEnd;
  }

  return (
    <div className={`md-glass w-full p-5 ${className}`}>
      <div className="md-glass-content mb-4 flex items-center justify-between">
        <button
          type="button"
          className="md-btn md-btn-ghost"
          disabled={monthIdx === 0}
          onClick={() => setMonthIdx(0)}
          aria-label="Previous month"
        >
          ←
        </button>
        <span className="text-sm font-semibold tracking-wide text-champagne">{MONTHS[monthIdx]}</span>
        <button
          type="button"
          className="md-btn md-btn-ghost"
          disabled={monthIdx === 1}
          onClick={() => setMonthIdx(1)}
          aria-label="Next month"
        >
          →
        </button>
      </div>
      <div className="md-glass-content grid grid-cols-7 gap-1 text-center">
        {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
          <div key={d} className="py-1 text-[10px] font-semibold tracking-wider text-app-faint">
            {d}
          </div>
        ))}
        {cells.map((dateKey, i) => {
          if (!dateKey) return <div key={`e-${i}`} />;
          const hasMatches = counts[dateKey] > 0;
          const inRange = inWindow(dateKey);
          const isSelected = selected === dateKey;
          const isToday = dateKey === today;

          return (
            <button
              key={dateKey}
              type="button"
              disabled={!inRange}
              onClick={() => hasMatches && onSelect(dateKey)}
              className={[
                "md-cal-cell py-1.5 text-xs tabular-nums",
                !inRange
                  ? "cursor-default text-app-faint"
                  : hasMatches
                    ? "md-cal-cell-has text-app-secondary"
                    : "text-app-faint",
                isSelected ? "md-cal-cell-selected" : "",
                isToday && !isSelected ? "md-cal-cell-today" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {parseInt(dateKey.slice(8), 10)}
              {hasMatches && (
                <span
                  className={[
                    "md-cal-badge",
                    isSelected ? "md-cal-badge-selected" : "md-cal-badge-default",
                  ].join(" ")}
                >
                  {counts[dateKey]}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
