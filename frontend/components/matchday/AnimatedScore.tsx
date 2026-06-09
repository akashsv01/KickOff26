"use client";

import { useEffect, useRef, useState } from "react";

export function AnimatedScore({
  value,
  large,
}: {
  value: number | null;
  large?: boolean;
}) {
  const prev = useRef<number | null>(value);
  const [flash, setFlash] = useState(false);
  const [pop, setPop] = useState(false);

  useEffect(() => {
    if (value != null && prev.current != null && value !== prev.current) {
      setFlash(true);
      setPop(true);
      const glowTimer = window.setTimeout(() => setFlash(false), 650);
      const popTimer = window.setTimeout(() => setPop(false), 380);
      prev.current = value;
      return () => {
        window.clearTimeout(glowTimer);
        window.clearTimeout(popTimer);
      };
    }
    prev.current = value;
  }, [value]);

  return (
    <span
      className={[
        "md-score tabular-nums",
        large ? "md-score-lg" : "",
        flash ? "md-score-flash" : "",
        pop ? "md-score-pop" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {value ?? "-"}
    </span>
  );
}
