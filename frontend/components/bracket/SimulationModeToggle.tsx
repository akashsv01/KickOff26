"use client";

import { useRef } from "react";

type Props = {
  /** false = Realistic (favour the stronger side), true = Upsets (more chaos). */
  upsets: boolean;
  onChange: (upsets: boolean) => void;
};

const OPTIONS = [
  { value: false, label: "Realistic", hint: "Outcomes favour the stronger side" },
  { value: true, label: "Upsets", hint: "More chaos - underdogs strike more often" },
] as const;

/**
 * Segmented toggle for the bracket simulation mode. Two equal-width segments in
 * one rounded pill with a sliding gold highlight, clearly legible in dark mode.
 * Exposed as a radiogroup with arrow-key switching and a visible focus ring.
 */
export function SimulationModeToggle({ upsets, onChange }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  function select(value: boolean) {
    onChange(value);
    // Move focus to the chosen segment so keyboard selection stays anchored.
    requestAnimationFrame(() => {
      const radios = ref.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]');
      radios?.[value ? 1 : 0]?.focus();
    });
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      select(true);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      select(false);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-app-muted">
        Simulation mode
      </span>
      <div
        ref={ref}
        role="radiogroup"
        aria-label="Simulation mode"
        onKeyDown={onKeyDown}
        className="relative inline-grid grid-cols-2 overflow-hidden rounded-full border border-app-faint/40 bg-app/10"
      >
        {/* Sliding highlight - clipped to the pill by the container. */}
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 w-1/2 bg-champagne shadow-[0_2px_10px_rgba(212,175,55,0.35)] transition-transform duration-200 ease-out"
          style={{ transform: upsets ? "translateX(100%)" : "translateX(0)" }}
        />
        {OPTIONS.map((opt) => {
          const active = opt.value === upsets;
          return (
            <button
              key={opt.label}
              type="button"
              role="radio"
              aria-checked={active}
              tabIndex={active ? 0 : -1}
              title={opt.hint}
              onClick={() => onChange(opt.value)}
              className={`relative z-10 min-w-[5.5rem] px-4 py-1.5 text-sm font-bold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-champagne ${
                active ? "text-[#1c1505]" : "text-app-secondary hover:text-app"
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
