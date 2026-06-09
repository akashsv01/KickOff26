"use client";

import type { FanPlanStop } from "@/components/FanPlanMap";
import { TeamFlag } from "@/components/TeamFlag";
import { formatUsdRange, stopTicketHigh, stopTicketLow } from "@/lib/fanplan";
import { CountryFlag } from "./CountryFlag";
import { IconPassport, IconPlane } from "./FanPlanIcons";

function formatKickoff(iso: string | null | undefined): string {
  if (!iso) return "Date TBD";
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function parseMatchTeams(label: string): [string, string] | null {
  const parts = label.split(/\s+vs\s+/i);
  if (parts.length === 2) return [parts[0].trim(), parts[1].trim()];
  return null;
}

type Props = {
  stops: FanPlanStop[];
};

export function FanPlanTimeline({ stops }: Props) {
  return (
    <ol className="fanplan-timeline">
      {stops.map((s, i) => {
        const teams = parseMatchTeams(s.match_label);
        const runningLow = stops.slice(0, i + 1).reduce((a, x) => a + stopTicketLow(x), 0);
        const runningHigh = stops.slice(0, i + 1).reduce((a, x) => a + stopTicketHigh(x), 0);
        const runningTravel = stops
          .slice(0, i + 1)
          .reduce((a, x) => a + (x.travel_from_prev_hours ?? 0), 0);
        const isLast = i === stops.length - 1;

        return (
          <li key={`${s.match_label}-${i}`} className="fanplan-timeline-item">
            <div className="fanplan-timeline-rail" aria-hidden="true">
              <span className="fanplan-timeline-node">{i + 1}</span>
              {!isLast ? <span className="fanplan-timeline-line" /> : null}
            </div>

            <article className="fanplan-stop-card">
              {s.travel_from_prev_hours != null && s.travel_from_prev_km != null ? (
                <div className="fanplan-travel-leg">
                  <IconPlane className="h-4 w-4 shrink-0 text-app-muted" />
                  <div>
                    <p className="fanplan-travel-leg-title">Est. travel from previous stop</p>
                    <p className="fanplan-travel-leg-body">
                      {s.travel_from_prev_km.toLocaleString()} km · {s.travel_from_prev_hours.toFixed(1)}h
                      <span className="text-app-faint"> · estimate, not a live schedule</span>
                    </p>
                  </div>
                </div>
              ) : null}

              <div className="fanplan-stop-header">
                <div className="flex items-center gap-2">
                  <CountryFlag country={s.country} className="h-3.5 w-5" />
                  <h3 className="fanplan-stop-city">
                    {s.city}
                    <span className="font-normal text-app-muted">, {s.country}</span>
                  </h3>
                </div>
                <span className="fanplan-ticket-pill">
                  {s.ticket_estimate?.display_range ??
                    formatUsdRange(stopTicketLow(s), stopTicketHigh(s))}
                </span>
              </div>

              <p className="fanplan-stadium">{s.stadium}</p>

              <div className="fanplan-fixture">
                {teams ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="fanplan-fixture-team">
                      <TeamFlag code={teams[0]} size="sm" />
                      <span className="md-team-code text-base">{teams[0]}</span>
                    </span>
                    <span className="text-xs font-semibold uppercase tracking-wider text-app-faint">
                      vs
                    </span>
                    <span className="fanplan-fixture-team">
                      <TeamFlag code={teams[1]} size="sm" />
                      <span className="md-team-code text-base">{teams[1]}</span>
                    </span>
                  </div>
                ) : (
                  <p className="text-sm font-semibold text-app">{s.match_label}</p>
                )}
                <p className="fanplan-fixture-date">{formatKickoff(s.kickoff_at)}</p>
              </div>

              <p className="fanplan-ticket-note">
                {s.ticket_estimate?.label ?? "Estimated"} · estimated — prices vary with dynamic
                pricing
              </p>

              {s.cross_border_note ? (
                <div className="fanplan-border-callout" role="note">
                  <IconPassport className="h-4 w-4 shrink-0" />
                  <p>{s.cross_border_note}</p>
                </div>
              ) : null}

              <p className="fanplan-running-total">
                Running totals — tickets: {formatUsdRange(runningLow, runningHigh)} · est. travel:{" "}
                {runningTravel.toFixed(1)}h
              </p>
            </article>
          </li>
        );
      })}
    </ol>
  );
}
