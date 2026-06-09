"use client";

import { TeamFlag } from "@/components/TeamFlag";
import { useAnimatedValue } from "@/components/matchday/useAnimatedValue";

export function ChampionProbList({
  probabilities,
  animate,
}: {
  probabilities: Record<string, number>;
  animate?: boolean;
}) {
  const sorted = Object.entries(probabilities)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);

  if (sorted.length === 0) {
    return <p className="text-sm text-app-muted">Run a simulation to see champion odds.</p>;
  }

  const maxPct = sorted[0][1] || 1;

  return (
    <ul className="sim-champ-list mt-3 space-y-2.5">
      {sorted.map(([code, pct]) => (
        <ChampionProbRow key={code} code={code} pct={pct} maxPct={maxPct} animate={animate} />
      ))}
    </ul>
  );
}

function ChampionProbRow({
  code,
  pct,
  maxPct,
  animate,
}: {
  code: string;
  pct: number;
  maxPct: number;
  animate?: boolean;
}) {
  const animatedPct = useAnimatedValue(pct, !!animate);
  const barWidth = maxPct > 0 ? (animatedPct / maxPct) * 100 : 0;

  return (
    <li className="sim-champ-row">
      <div className="flex min-w-0 items-center gap-2">
        <TeamFlag code={code} size="xs" className="shadow-none" />
        <span className="truncate font-bold text-app">{code}</span>
      </div>
      <div className="sim-champ-bar-track">
        <div className="sim-champ-bar-fill" style={{ width: `${Math.min(100, barWidth)}%` }} />
      </div>
      <span className="sim-champ-pct tabular-nums">{animatedPct.toFixed(1)}%</span>
    </li>
  );
}
