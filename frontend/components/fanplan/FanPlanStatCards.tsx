"use client";

import { formatUsdRange } from "@/lib/fanplan";
import { IconMatches, IconRoute, IconTicket } from "./FanPlanIcons";

type Props = {
  ticketLow: number;
  ticketHigh: number;
  travelHours: number;
  travelKm: number;
  matchCount: number;
};

export function FanPlanStatCards({
  ticketLow,
  ticketHigh,
  travelHours,
  travelKm,
  matchCount,
}: Props) {
  return (
    <div className="fanplan-stat-grid">
      <article className="fanplan-stat-card">
        <div className="fanplan-stat-icon fanplan-stat-icon-gold">
          <IconTicket className="h-5 w-5" />
        </div>
        <p className="fanplan-stat-label">Est. tickets</p>
        <p className="fanplan-stat-value">{formatUsdRange(ticketLow, ticketHigh)}</p>
        <p className="fanplan-stat-sub">Estimated range · dynamic pricing</p>
      </article>

      <article className="fanplan-stat-card">
        <div className="fanplan-stat-icon fanplan-stat-icon-cool">
          <IconRoute className="h-5 w-5" />
        </div>
        <p className="fanplan-stat-label">Est. travel</p>
        <p className="fanplan-stat-value">
          {travelHours.toFixed(1)}h
          <span className="fanplan-stat-value-sub">({travelKm.toLocaleString()} km)</span>
        </p>
        <p className="fanplan-stat-sub">Great-circle distance · not live schedules</p>
      </article>

      <article className="fanplan-stat-card">
        <div className="fanplan-stat-icon fanplan-stat-icon-pitch">
          <IconMatches className="h-5 w-5" />
        </div>
        <p className="fanplan-stat-label">Matches</p>
        <p className="fanplan-stat-value">{matchCount}</p>
        <p className="fanplan-stat-sub">On your optimized route</p>
      </article>
    </div>
  );
}
