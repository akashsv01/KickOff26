"use client";

import { useMemo, useState } from "react";
import { FootballLoader } from "@/components/FootballLoader";
import { TeamFlag } from "@/components/TeamFlag";
import type { Team } from "@/lib/matchday";

export function FollowPicker({
  teams,
  followed,
  onToggle,
  onSave,
  saving,
  savedMessage,
}: {
  teams: Team[];
  followed: number[];
  onToggle: (id: number) => void;
  onSave: () => void;
  saving?: boolean;
  savedMessage?: string | null;
}) {
  const [query, setQuery] = useState("");

  const grouped = useMemo(() => {
    const filtered = teams.filter(
      (t) =>
        !query ||
        t.code.toLowerCase().includes(query.toLowerCase()) ||
        t.name.toLowerCase().includes(query.toLowerCase())
    );
    const map: Record<string, Team[]> = {};
    for (const t of filtered) {
      const g = t.group_letter ?? "?";
      map[g] = map[g] ?? [];
      map[g].push(t);
    }
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
  }, [teams, query]);

  return (
    <div className="md-glass p-5 md-animate-in">
      <div className="relative z-[1] flex flex-wrap items-center justify-between gap-3">
        <h2 className="md-section-title">Pick teams to follow</h2>
        {savedMessage && (
          <span className="text-sm font-medium tabular-nums text-green-400">{savedMessage}</span>
        )}
      </div>
      <input
        type="search"
        placeholder="Search teams…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="md-input relative z-[1] mt-4"
      />
      <div className="relative z-[1] mt-4 max-h-80 space-y-4 overflow-y-auto">
        {grouped.map(([group, list]) => (
          <div key={group}>
            <h3 className="md-label mb-2 text-champagne/90">Group {group}</h3>
            <div className="flex flex-wrap gap-2">
              {list.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onToggle(t.id)}
                  className={[
                    "md-team-chip",
                    followed.includes(t.id) ? "md-team-chip-selected" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <TeamFlag code={t.code} size="xs" />
                  {t.code}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <button
        className="md-btn md-btn-primary relative z-[1] mt-5 w-full sm:w-auto"
        onClick={onSave}
        disabled={saving}
      >
        {saving ? (
          <FootballLoader size="sm" label="Saving…" />
        ) : (
          `Save (${followed.length} teams)`
        )}
      </button>
    </div>
  );
}
