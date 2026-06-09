"use client";

import { useEffect, useRef } from "react";
import { TeamFlag } from "@/components/TeamFlag";

async function fireChampionConfetti() {
  if (typeof window === "undefined") return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) return;

  const { default: confetti } = await import("canvas-confetti");

  const duration = 2800;
  const end = Date.now() + duration;
  const colors = ["#c9a227", "#f4e4a6", "#2d5a27", "#ffffff", "#1a3d16"];

  const frame = () => {
    confetti({
      particleCount: 3,
      angle: 60,
      spread: 55,
      origin: { x: 0, y: 0.55 },
      colors,
      disableForReducedMotion: true,
      zIndex: 9999,
    });
    confetti({
      particleCount: 3,
      angle: 120,
      spread: 55,
      origin: { x: 1, y: 0.55 },
      colors,
      disableForReducedMotion: true,
      zIndex: 9999,
    });

    if (Date.now() < end) {
      requestAnimationFrame(frame);
    }
  };

  confetti({
    particleCount: 80,
    spread: 100,
    origin: { y: 0.45 },
    colors,
    disableForReducedMotion: true,
    zIndex: 9999,
  });
  frame();
}

export function ChampionCelebration({
  championCode,
  teamName,
}: {
  championCode: string;
  teamName?: string;
}) {
  const prevCode = useRef<string | null>(null);

  useEffect(() => {
    if (!championCode) {
      prevCode.current = null;
      return;
    }
    if (prevCode.current === championCode) return;
    prevCode.current = championCode;
    fireChampionConfetti();
  }, [championCode]);

  if (!championCode) return null;

  const displayName = teamName || championCode;

  return (
    <div
      className="champion-banner mb-4 flex items-center justify-center gap-4 rounded-xl border border-champagne/50 bg-champagne/10 px-5 py-4 shadow-[0_0_24px_var(--app-gold-glow)]"
      role="status"
      aria-live="polite"
    >
      <span className="text-3xl" aria-hidden>
        🏆
      </span>
      <TeamFlag code={championCode} size="md" className="shadow-none" />
      <div className="text-left">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-champagne">Champion!</p>
        <p className="text-lg font-bold text-app">{displayName}</p>
        <p className="text-xs font-semibold tracking-wide text-app-muted">{championCode}</p>
      </div>
      <span className="text-3xl" aria-hidden>
        🏆
      </span>
    </div>
  );
}
