"use client";

import { useEffect, useState, type CSSProperties } from "react";
import type { ReactionBurst } from "@/lib/watch";

export function FloatingReactions({ bursts }: { bursts: ReactionBurst[] }) {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = () => setReducedMotion(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  if (reducedMotion || bursts.length === 0) return null;

  return (
    <div className="watch-float-layer" aria-hidden>
      {bursts.map((b) => (
        <span
          key={b.id}
          className="watch-float-emoji"
          style={
            {
              left: `${b.x}%`,
              "--drift": `${b.drift}px`,
            } as CSSProperties
          }
        >
          {b.emoji}
        </span>
      ))}
    </div>
  );
}
