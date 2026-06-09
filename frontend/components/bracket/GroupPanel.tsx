"use client";

import { TeamFlag } from "@/components/TeamFlag";
import type { GroupFixture, GroupResults, MatchResult, StandingRow } from "@/lib/bracketGroups";
import { quickResult } from "@/lib/bracketGroups";

type Team = { id: number; name: string; code: string; elo: number };

function formatKickoff(iso: string | null) {
  if (!iso) return "TBD";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function FixtureRow({
  fixture,
  result,
  onSetResult,
  homeElo,
  awayElo,
}: {
  fixture: GroupFixture & {
    kickoff_at?: string | null;
    city?: string | null;
    status?: string;
  };
  result: MatchResult | null | undefined;
  onSetResult: (fixtureId: number, result: MatchResult | null) => void;
  homeElo: number;
  awayElo: number;
}) {
  const hs = result?.home_score ?? "";
  const aws = result?.away_score ?? "";

  function updateScore(side: "home" | "away", raw: string) {
    const parsed = raw === "" ? null : Math.max(0, Math.min(9, parseInt(raw, 10) || 0));
    const nextHome = side === "home" ? parsed : (result?.home_score ?? null);
    const nextAway = side === "away" ? parsed : (result?.away_score ?? null);
    if (nextHome == null && nextAway == null) {
      onSetResult(fixture.id, null);
      return;
    }
    onSetResult(fixture.id, {
      home_score: nextHome ?? 0,
      away_score: nextAway ?? 0,
    });
  }

  return (
    <div className="rounded-lg border border-app-faint/30 bg-app/10 px-3 py-2.5 text-sm shadow-sm">
      <div className="space-y-2">
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          <span className="inline-flex min-w-0 items-center gap-1.5 font-semibold text-app">
            <TeamFlag code={fixture.home.code} size="xs" />
            <span className="truncate">{fixture.home.code}</span>
            {homeElo > awayElo ? (
              <span className="shrink-0 rounded bg-champagne/25 px-1 py-0.5 text-[10px] font-medium text-champagne">
                Fav
              </span>
            ) : null}
          </span>

          <div className="inline-flex items-center gap-1">
            <input
              type="number"
              min={0}
              max={9}
              aria-label={`${fixture.home.code} goals`}
              className="w-10 rounded border border-app-faint/40 bg-app/20 px-1 py-0.5 text-center tabular-nums text-app"
              value={hs}
              onChange={(e) => updateScore("home", e.target.value)}
            />
            <span className="text-app-faint">-</span>
            <input
              type="number"
              min={0}
              max={9}
              aria-label={`${fixture.away.code} goals`}
              className="w-10 rounded border border-app-faint/40 bg-app/20 px-1 py-0.5 text-center tabular-nums text-app"
              value={aws}
              onChange={(e) => updateScore("away", e.target.value)}
            />
          </div>

          <span className="inline-flex min-w-0 items-center justify-end gap-1.5 font-semibold text-app">
            {awayElo > homeElo ? (
              <span className="shrink-0 rounded bg-champagne/25 px-1 py-0.5 text-[10px] font-medium text-champagne">
                Fav
              </span>
            ) : null}
            <span className="truncate">{fixture.away.code}</span>
            <TeamFlag code={fixture.away.code} size="xs" />
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs text-app-faint">
            {formatKickoff(fixture.kickoff_at ?? null)}
            {fixture.city ? ` · ${fixture.city}` : ""}
          </div>

          {result ? (
            <button
              type="button"
              className="rounded px-2 py-0.5 text-[10px] font-semibold text-app-faint hover:text-app"
              onClick={() => onSetResult(fixture.id, null)}
            >
              Clear
            </button>
          ) : null}
        </div>

        <div className="grid grid-cols-3 gap-1.5">
          {(["home", "draw", "away"] as const).map((outcome) => (
            <button
              key={outcome}
              type="button"
              className="rounded border border-app-faint/40 bg-app/5 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-app transition hover:border-champagne/55 hover:text-champagne"
              onClick={() => onSetResult(fixture.id, quickResult(outcome))}
            >
              {outcome === "home" ? "Home" : outcome === "away" ? "Away" : "Draw"}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function GroupPanel({
  group,
  teams,
  standings,
  fixtures,
  expanded,
  onToggle,
  groupResults,
  onSetResult,
  onRandomizeGroup,
  thirdAdvancers,
}: {
  group: string;
  teams: Team[];
  standings: StandingRow[];
  fixtures: (GroupFixture & { kickoff_at?: string | null; city?: string | null; status?: string })[];
  expanded: boolean;
  onToggle: () => void;
  groupResults: GroupResults;
  onSetResult: (fixtureId: number, result: MatchResult | null) => void;
  onRandomizeGroup: () => void;
  thirdAdvancers: Set<string>;
}) {
  const rows =
    standings.length > 0
      ? standings
      : teams.map((t, i) => ({
          code: t.code,
          name: t.name,
          played: 0,
          won: 0,
          drawn: 0,
          lost: 0,
          gf: 0,
          ga: 0,
          gd: 0,
          points: 0,
          rank: i + 1,
        }));
  const eloByCode = Object.fromEntries(teams.map((t) => [t.code, t.elo]));

  return (
    <div className="md-glass border border-app-faint/45 shadow-[0_14px_34px_rgba(0,0,0,0.16)]">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-app/7"
      >
        <span className="text-lg font-black tracking-wide text-app">Group {group}</span>
        <span className="text-xs font-semibold text-champagne">{expanded ? "Hide Fixtures ▲" : "Show Fixtures ▼"}</span>
      </button>

      <div className="border-t border-app-faint/20 px-4 pb-4 pt-2">
        <div className="overflow-x-hidden">
          <table className="w-full table-fixed text-xs sm:text-sm">
            <colgroup>
              <col className="w-[30px]" />
              <col />
              <col className="w-[48px]" />
              <col className="w-[48px]" />
              <col className="w-[28px]" />
              <col className="w-[28px]" />
              <col className="w-[28px]" />
              <col className="w-[28px]" />
              <col className="w-[36px]" />
              <col className="w-[42px]" />
            </colgroup>
            <thead>
              <tr className="border-b border-app-faint/25 uppercase tracking-wide text-app">
                <th className="py-2 text-left font-bold">#</th>
                <th className="py-2 text-left font-bold">Team</th>
                <th className="px-0.5 py-2 text-center font-bold">Q</th>
                <th className="px-0.5 py-2 text-right font-bold">Rtg</th>
                <th className="px-0.5 py-2 text-center font-bold">P</th>
                <th className="px-0.5 py-2 text-center font-bold">W</th>
                <th className="px-0.5 py-2 text-center font-bold">D</th>
                <th className="px-0.5 py-2 text-center font-bold">L</th>
                <th className="px-0.5 py-2 text-center font-bold">GD</th>
                <th className="px-0.5 py-2 text-center font-bold text-champagne">Pts</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isTopTwo = row.rank <= 2;
                const isBestThird = row.rank === 3 && thirdAdvancers.has(row.code);
                return (
                  <tr
                    key={row.code}
                    className={`border-b border-app-faint/10 ${
                      isTopTwo
                        ? "bg-emerald-500/16"
                        : isBestThird
                          ? "bg-amber-500/14"
                          : ""
                    }`}
                  >
                    <td className="py-2 font-semibold text-app">{row.rank}</td>
                    <td className="py-2">
                      <span className="inline-flex min-w-0 items-center gap-2">
                        <TeamFlag code={row.code} size="xs" className="shadow-none" />
                        <span className="font-extrabold text-app">{row.code}</span>
                      </span>
                    </td>
                    <td className="px-0.5 py-2 text-center">
                      {isTopTwo ? (
                        <span className="inline-flex min-w-6 justify-center rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                          Q
                        </span>
                      ) : isBestThird ? (
                        <span className="inline-flex min-w-10 justify-center rounded border border-amber-700/70 bg-amber-500/25 px-1 py-0.5 text-[10px] font-bold uppercase text-app">
                          3RD+
                        </span>
                      ) : (
                        <span className="text-app-faint">-</span>
                      )}
                    </td>
                    <td className="px-0.5 py-2 text-right text-[11px] font-medium text-app-muted">
                      {Math.round(eloByCode[row.code] ?? 0)}
                    </td>
                    <td className="px-0.5 py-2 text-center text-app">{row.played}</td>
                    <td className="px-0.5 py-2 text-center text-app">{row.won}</td>
                    <td className="px-0.5 py-2 text-center text-app">{row.drawn}</td>
                    <td className="px-0.5 py-2 text-center text-app">{row.lost}</td>
                    <td className="px-0.5 py-2 text-center text-app">{row.gd}</td>
                    <td className="px-0.5 py-2 text-center font-extrabold text-app">{row.points}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {expanded && (
          <div className="mt-4 space-y-2 border-t border-app-faint/20 pt-3">
            <div className="mb-1 flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-app">Fixtures</h4>
              <button type="button" className="md-btn-secondary text-xs" onClick={onRandomizeGroup}>
                Randomize Group
              </button>
            </div>
            {fixtures.map((f) => (
              <FixtureRow
                key={f.id}
                fixture={f}
                result={groupResults[f.id]}
                onSetResult={onSetResult}
                homeElo={eloByCode[f.home.code] ?? 0}
                awayElo={eloByCode[f.away.code] ?? 0}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
