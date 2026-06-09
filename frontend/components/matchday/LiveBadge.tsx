"use client";

export function LiveBadge({ minute }: { minute?: number | null }) {
  return (
    <span className="md-live-badge">
      <span className="md-live-dot" aria-hidden />
      Live{minute != null ? ` · ${minute}'` : ""}
    </span>
  );
}
