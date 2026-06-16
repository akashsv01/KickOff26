/**
 * Reusable match-status pill. LIVE is the loudest (red + pulsing dot); FT is a
 * muted secondary pill; scheduled renders nothing (kept minimal - callers show
 * the group label separately). Reuse anywhere a match status is shown.
 */
export function MatchStatusBadge({
  status,
  minute,
}: {
  status: string;
  minute?: number | null;
}) {
  if (status === "live") {
    return (
      <span className="match-badge match-badge-live" aria-label={minute ? `Live, ${minute} minutes` : "Live"}>
        <span className="match-badge-dot" aria-hidden />
        {minute ? `LIVE ${minute}'` : "LIVE"}
      </span>
    );
  }
  if (status === "finished") {
    return <span className="match-badge match-badge-ft">FT</span>;
  }
  return null;
}
