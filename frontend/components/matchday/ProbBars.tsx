"use client";

import { useAnimatedValue } from "./useAnimatedValue";

const VARIANTS = {
  home: "md-prob-fill-home",
  draw: "md-prob-fill-draw",
  away: "md-prob-fill-away",
} as const;

export function ProbBars({
  home,
  draw,
  away,
  animate,
}: {
  home: number;
  draw: number;
  away: number;
  animate?: boolean;
}) {
  return (
    <div className="space-y-2">
      <ProbBar label="H" prob={home} variant="home" animate={animate} />
      <ProbBar label="D" prob={draw} variant="draw" animate={animate} />
      <ProbBar label="A" prob={away} variant="away" animate={animate} />
    </div>
  );
}

function ProbBar({
  label,
  prob,
  variant,
  animate,
}: {
  label: string;
  prob: number;
  variant: keyof typeof VARIANTS;
  animate?: boolean;
}) {
  const animated = useAnimatedValue(prob, !!animate);
  const pct = Math.max(0, Math.min(100, animated * 100));

  return (
    <div className="md-prob-row">
      <span className="md-prob-label">{label}</span>
      <div className="md-prob-track">
        <div
          className={`md-prob-fill ${VARIANTS[variant]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="md-prob-pct">{pct.toFixed(0)}%</span>
    </div>
  );
}
