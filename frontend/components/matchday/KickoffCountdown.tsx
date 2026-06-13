"use client";

import { useEffect, useState } from "react";

const DAY_MS = 24 * 60 * 60 * 1000;

function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

/**
 * Ticking HH:MM:SS countdown shown within ~24h of kickoff.
 *
 * Driven by the absolute kickoff timestamp (UTC) vs now, so it is correct in
 * any viewer timezone. Renders nothing when the match is more than 24h away or
 * kickoff has passed (the card then shows LIVE / FT from live data). Ticks once
 * per second only while inside the window and clears its timer on unmount.
 */
export function KickoffCountdown({ kickoffIso }: { kickoffIso: string | null | undefined }) {
  const target = kickoffIso ? new Date(kickoffIso).getTime() : NaN;
  const [now, setNow] = useState(() => Date.now());

  const remaining = target - now;
  const withinWindow = Number.isFinite(target) && remaining > 0 && remaining <= DAY_MS;

  useEffect(() => {
    if (!Number.isFinite(target)) return;
    const remain = target - Date.now();
    if (remain <= 0) return; // kickoff passed - parent switches to LIVE/FT
    if (remain > DAY_MS) {
      // Sleep until we enter the 24h window, then re-evaluate (starts ticking).
      const id = setTimeout(() => setNow(Date.now()), remain - DAY_MS + 250);
      return () => clearTimeout(id);
    }
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [target, withinWindow]);

  if (!withinWindow) return null;

  return (
    <span
      className="md-countdown"
      role="timer"
      aria-label={`Kicks off in ${formatRemaining(remaining)}`}
    >
      <span className="md-countdown-dot" aria-hidden="true" />
      {formatRemaining(remaining)}
    </span>
  );
}
