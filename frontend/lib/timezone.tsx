"use client";

import { useMemo } from "react";
import { useAuth } from "@/lib/auth";
import { detectBrowserTimezone } from "@/lib/signupProfile";

/**
 * The active display timezone for kickoff times.
 *
 * - Logged-out: the browser's local zone - the historical default, unchanged.
 * - Logged-in: the user's resolved zone (`user.timezone`), which the backend
 *   captures at signup (browser-detected) and backfills from the country map,
 *   falling back to UTC. This mirrors backend `resolve_timezone(user)`.
 *
 * Reads from the auth context, so it re-renders immediately on login/logout.
 */
export function useDisplayTimezone(): string {
  const { user } = useAuth();
  return useMemo(() => {
    if (user) return user.resolved_timezone || user.timezone || "UTC";
    return detectBrowserTimezone() || "UTC";
  }, [user]);
}

/** Short zone abbreviation for a label, e.g. "EST", "GMT+1", "JST". */
export function timezoneAbbrev(zone: string, at: Date = new Date()): string {
  try {
    const parts = new Intl.DateTimeFormat(undefined, {
      timeZone: zone,
      timeZoneName: "short",
    }).formatToParts(at);
    const name = parts.find((p) => p.type === "timeZoneName")?.value;
    if (name) return name;
  } catch {
    /* fall through */
  }
  return zone;
}

/** "All times shown in <ABBR>" footer label, reacting to login/logout. */
export function TimesInZoneLabel({ className }: { className?: string }) {
  const zone = useDisplayTimezone();
  const abbr = timezoneAbbrev(zone);
  return (
    <p className={className ?? "mt-4 text-center text-xs text-app-faint"}>
      All times shown in {abbr}
      {abbr !== zone ? ` (${zone})` : ""}
    </p>
  );
}
