"use client";

import type { ReactNode, MouseEvent, KeyboardEvent } from "react";

type GlassVariant = "default" | "live";

export function GlassCard({
  variant = "default",
  interactive,
  className = "",
  children,
  ...props
}: {
  variant?: GlassVariant;
  interactive?: boolean;
  className?: string;
  children: ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={[
        "md-glass",
        interactive ? "md-glass-interactive" : "",
        variant === "live" ? "md-glass-live" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...props}
    >
      <div className="md-glass-content">{children}</div>
    </div>
  );
}

export function glassCardClass(variant: GlassVariant = "default", interactive?: boolean) {
  return [
    "md-glass",
    interactive ? "md-glass-interactive" : "",
    variant === "live" ? "md-glass-live" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function matchCardKeyDown(
  e: KeyboardEvent,
  navigate: () => void
): void {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    navigate();
  }
}

export function matchCardClick(
  e: MouseEvent,
  navigate: () => void
): void {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  navigate();
}
