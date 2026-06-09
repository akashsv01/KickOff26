import type { FanPlanStop } from "@/components/FanPlanMap";

export type Itinerary = {
  stops: FanPlanStop[];
  total_ticket_cost_low_usd: number;
  total_ticket_cost_high_usd: number;
  total_travel_hours: number;
  total_travel_km: number;
  disclaimer: string;
  notes: string[];
};

type RawTicketEstimate = {
  low_usd?: number;
  high_usd?: number;
  label?: string;
  display_range?: string;
  is_estimate?: boolean;
};

type RawStop = {
  city: string;
  country: string;
  match_label: string;
  stadium: string;
  kickoff_at?: string | null;
  lat: number;
  lng: number;
  travel_from_prev_km?: number | null;
  travel_from_prev_hours?: number | null;
  ticket_estimate?: RawTicketEstimate;
  ticket_cost_usd?: number | null;
  cross_border_note?: string | null;
};

function normalizeTicketEstimate(raw: RawStop): FanPlanStop["ticket_estimate"] {
  const est = raw.ticket_estimate;
  if (est && typeof est.low_usd === "number" && typeof est.high_usd === "number") {
    return {
      low_usd: est.low_usd,
      high_usd: est.high_usd,
      label: est.label ?? "Estimated",
      display_range:
        est.display_range ?? `est. $${est.low_usd.toLocaleString()}–$${est.high_usd.toLocaleString()}`,
      is_estimate: est.is_estimate ?? true,
    };
  }

  const legacy = typeof raw.ticket_cost_usd === "number" ? raw.ticket_cost_usd : 200;
  return {
    low_usd: legacy,
    high_usd: legacy,
    label: "Estimated",
    display_range: `est. $${legacy.toLocaleString()}`,
    is_estimate: true,
  };
}

function normalizeStop(raw: RawStop): FanPlanStop {
  return {
    city: raw.city,
    country: raw.country,
    match_label: raw.match_label,
    stadium: raw.stadium,
    kickoff_at: raw.kickoff_at,
    lat: raw.lat,
    lng: raw.lng,
    travel_from_prev_km: raw.travel_from_prev_km ?? null,
    travel_from_prev_hours: raw.travel_from_prev_hours ?? null,
    ticket_estimate: normalizeTicketEstimate(raw),
    cross_border_note: raw.cross_border_note ?? null,
  };
}

/** Normalize API payload — handles legacy responses missing range totals. */
export function normalizeItinerary(raw: Record<string, unknown>): Itinerary {
  const stops = Array.isArray(raw.stops)
    ? (raw.stops as RawStop[]).map(normalizeStop)
    : [];

  let low = raw.total_ticket_cost_low_usd;
  let high = raw.total_ticket_cost_high_usd;

  if (typeof low !== "number" || typeof high !== "number") {
    low = stops.reduce((sum, s) => sum + s.ticket_estimate.low_usd, 0);
    high = stops.reduce((sum, s) => sum + s.ticket_estimate.high_usd, 0);
  }

  const legacyTotal = raw.total_cost_usd;
  if (typeof high !== "number" && typeof legacyTotal === "number") {
    high = legacyTotal;
    low = typeof low === "number" ? low : legacyTotal;
  }

  return {
    stops,
    total_ticket_cost_low_usd: Number(low) || 0,
    total_ticket_cost_high_usd: Number(high) || 0,
    total_travel_hours: typeof raw.total_travel_hours === "number" ? raw.total_travel_hours : 0,
    total_travel_km: typeof raw.total_travel_km === "number" ? raw.total_travel_km : 0,
    disclaimer:
      typeof raw.disclaimer === "string"
        ? raw.disclaimer
        : "Ticket prices are estimates based on published reporting. FIFA uses dynamic pricing.",
    notes: Array.isArray(raw.notes) ? (raw.notes as string[]) : [],
  };
}

export function formatUsdRange(low: number | undefined, high: number | undefined): string {
  const lo = typeof low === "number" && Number.isFinite(low) ? low : 0;
  const hi = typeof high === "number" && Number.isFinite(high) ? high : lo;
  return `est. $${lo.toLocaleString()}–$${hi.toLocaleString()}`;
}

export function stopTicketLow(stop: FanPlanStop): number {
  return stop.ticket_estimate?.low_usd ?? 0;
}

export function stopTicketHigh(stop: FanPlanStop): number {
  return stop.ticket_estimate?.high_usd ?? 0;
}
