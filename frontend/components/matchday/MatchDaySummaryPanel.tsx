"use client";

import { useRouter } from "next/navigation";
import { formatTodayLabel, navigateToMatchDetail, type Match } from "@/lib/matchday";

export function MatchDaySummaryPanel({
  liveCount,
  liveMatch,
}: {
  liveCount: number;
  liveMatch?: Match | null;
}) {
  const router = useRouter();
  const todayLabel = formatTodayLabel();

  return (
    <div className="md-glass p-4">
      <div className="md-glass-content space-y-4">
        <div>
          <p className="md-label">Today</p>
          <p className="mt-1 text-sm font-medium leading-snug text-app-secondary">{todayLabel}</p>
        </div>

        <div className="flex items-center justify-between border-t border-white/8 pt-4">
          <span className="text-sm text-app-muted">Live now</span>
          {liveCount > 0 ? (
            <span className="md-live-indicator tabular-nums">
              <span className="md-live-indicator-dot" aria-hidden />
              {liveCount}
            </span>
          ) : (
            <span className="text-sm tabular-nums text-app-faint">0</span>
          )}
        </div>

        {liveMatch && (
          <button
            type="button"
            className="md-btn md-btn-secondary w-full text-sm"
            onClick={() => navigateToMatchDetail(router.push, liveMatch.id)}
          >
            Jump to live match
          </button>
        )}
      </div>
    </div>
  );
}
