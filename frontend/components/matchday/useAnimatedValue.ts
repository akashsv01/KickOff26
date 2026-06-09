"use client";

import { useEffect, useRef, useState } from "react";

export function useAnimatedValue(target: number, enabled: boolean, duration = 700) {
  const [display, setDisplay] = useState(target);
  const displayRef = useRef(target);

  useEffect(() => {
    displayRef.current = display;
  });

  useEffect(() => {
    if (!enabled) {
      setDisplay(target);
      displayRef.current = target;
      return;
    }

    const start = displayRef.current;
    const diff = target - start;
    if (Math.abs(diff) < 0.0005) {
      setDisplay(target);
      displayRef.current = target;
      return;
    }

    const startTime = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const t = Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = start + diff * eased;
      setDisplay(next);
      displayRef.current = next;
      if (t < 1) raf = requestAnimationFrame(tick);
      else {
        setDisplay(target);
        displayRef.current = target;
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, enabled, duration]);

  return display;
}
