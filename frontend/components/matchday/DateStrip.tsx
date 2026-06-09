"use client";

import { formatDayLabel } from "@/lib/matchday";

export function DateStrip({
  days,
  selected,
  onSelect,
}: {
  days: { date: string; match_count: number }[];
  selected: string;
  onSelect: (date: string) => void;
}) {
  if (!days.length) return null;

  return (
    <div className="md-glass p-3 lg:hidden">
      <div className="md-glass-content flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {days.map((d) => {
          const isSelected = selected === d.date;
          return (
            <button
              key={d.date}
              type="button"
              onClick={() => onSelect(d.date)}
              className={[
                "md-cal-cell shrink-0 px-3 py-2 text-left",
                isSelected ? "md-cal-cell-selected" : "md-cal-cell-has",
              ].join(" ")}
            >
              <div className="text-[10px] font-semibold uppercase tracking-wider text-app-muted">
                {d.date.slice(8)}/{d.date.slice(5, 7)}
              </div>
              <div className="mt-0.5 text-xs font-semibold text-app-secondary">
                {formatDayLabel(d.date).split(",")[0]}
              </div>
              <div className="mt-1 text-[10px] tabular-nums text-champagne">
                {d.match_count} {d.match_count === 1 ? "match" : "matches"}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
