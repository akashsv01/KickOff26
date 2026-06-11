"use client";

import { useId } from "react";
import {
  BASE1_RECT,
  BASE2_RECT,
  BOWL_D,
  HANDLE_L_D,
  HANDLE_R_D,
  RIM_RECT,
  STAR_POINTS,
  STEM_D,
  TROPHY_VIEWBOX,
} from "@/lib/trophyPaths";

/**
 * Original KickOff26 championship trophy - theme-aware gold gradient.
 * Uses the shared geometry so the navbar logo and the favicon stay identical.
 */
export function TrophyIcon({ className }: { className?: string }) {
  const gid = useId();

  return (
    <svg
      viewBox={TROPHY_VIEWBOX}
      className={className}
      role="img"
      aria-label="KickOff26 trophy"
      focusable="false"
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--app-gold-light)" />
          <stop offset="0.55" stopColor="var(--app-gold)" />
          <stop offset="1" stopColor="var(--app-gold-dark)" />
        </linearGradient>
      </defs>
      <g fill={`url(#${gid})`}>
        <polygon points={STAR_POINTS} opacity={0.92} />
        <rect x={RIM_RECT.x} y={RIM_RECT.y} width={RIM_RECT.width} height={RIM_RECT.height} rx={RIM_RECT.rx} />
        <path d={BOWL_D} />
        <path d={HANDLE_L_D} />
        <path d={HANDLE_R_D} />
        <path d={STEM_D} />
        <rect x={BASE1_RECT.x} y={BASE1_RECT.y} width={BASE1_RECT.width} height={BASE1_RECT.height} rx={BASE1_RECT.rx} />
        <rect x={BASE2_RECT.x} y={BASE2_RECT.y} width={BASE2_RECT.width} height={BASE2_RECT.height} rx={BASE2_RECT.rx} />
      </g>
    </svg>
  );
}
