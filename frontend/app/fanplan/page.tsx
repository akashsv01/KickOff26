"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { AppToast } from "@/components/AppToast";
import { FanPlanControls } from "@/components/fanplan/FanPlanControls";
import { FanPlanInfoNotes, FanPlanSkipped } from "@/components/fanplan/FanPlanSkipped";
import { FanPlanStatCards } from "@/components/fanplan/FanPlanStatCards";
import { FanPlanTimeline } from "@/components/fanplan/FanPlanTimeline";
import { exportItineraryToPdf } from "@/lib/exporters";
import { formatUsdRange, normalizeItinerary, type Itinerary } from "@/lib/fanplan";
import { formatKickoff } from "@/lib/matchday";
import { useDisplayTimezone } from "@/lib/timezone";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const FanPlanMap = dynamic(() => import("@/components/FanPlanMap"), { ssr: false });

type Team = { id: number; name: string; code: string };

export default function FanPlanPage() {
  const { user } = useAuth();
  const zone = useDisplayTimezone();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [plan, setPlan] = useState<Itinerary | null>(null);
  const [maxCities, setMaxCities] = useState(5);
  const [budget, setBudget] = useState<number | "">("");
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [errorToast, setErrorToast] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Team[]>("/teams").then(setTeams).catch(console.error);
  }, []);

  function toggleTeam(id: number) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function generate() {
    if (!user) {
      setLoginPrompt(true);
      return;
    }
    if (selected.length === 0) {
      setErrorToast("Select at least one team to follow.");
      return;
    }
    try {
      const data = await api<Record<string, unknown>>("/fanplan/itinerary", {
        method: "POST",
        body: JSON.stringify({
          team_ids: selected,
          max_cities: maxCities,
          budget_usd: budget === "" ? null : Number(budget),
        }),
      });
      setPlan(normalizeItinerary(data));
    } catch (err) {
      setErrorToast(err instanceof Error ? err.message : "Failed to generate itinerary");
    }
  }

  const skippedNotes = plan?.notes.filter((n) => n.startsWith("Skipped")) ?? [];
  const infoNotes = plan?.notes.filter((n) => !n.startsWith("Skipped")) ?? [];

  async function exportPdf() {
    if (!plan || plan.stops.length === 0) return;
    setExporting(true);
    try {
      const cityCount = new Set(plan.stops.map((s) => s.city)).size;
      await exportItineraryToPdf(
        {
          title: "KickOff26 Travel Planner Itinerary",
          username: user?.username,
          subtitle: `${plan.stops.length} matches across ${cityCount} host cities`,
          stops: plan.stops.map((s, i) => ({
            index: i + 1,
            city: s.city,
            country: s.country,
            venue: s.stadium,
            fixture: s.match_label,
            date: s.kickoff_at ? formatKickoff(s.kickoff_at, zone) : null,
            ticketRange: s.ticket_estimate?.display_range ?? formatUsdRange(
              s.ticket_estimate?.low_usd,
              s.ticket_estimate?.high_usd
            ),
            travelLeg:
              i === 0
                ? "Trip start"
                : s.travel_from_prev_km
                ? `${Math.round(s.travel_from_prev_km).toLocaleString()} km, ~${(
                    s.travel_from_prev_hours ?? 0
                  ).toFixed(1)} h from previous stop`
                : null,
          })),
          totals: [
            { label: "Matches", value: String(plan.stops.length) },
            {
              label: "Tickets (est.)",
              value: formatUsdRange(
                plan.total_ticket_cost_low_usd,
                plan.total_ticket_cost_high_usd
              ),
            },
            {
              label: "Total travel",
              value: `${Math.round(plan.total_travel_km).toLocaleString()} km, ~${plan.total_travel_hours.toFixed(
                1
              )} h`,
            },
          ],
          disclaimer: plan.disclaimer,
          mapNode: mapRef.current,
        },
        "kickoff26-itinerary.pdf"
      );
    } catch {
      setErrorToast("Export failed - try again.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="fanplan-shell matchday-shell space-y-8 pb-10">
      {loginPrompt ? (
        <AppToast
          message="Please log in to generate and save your fan itinerary."
          onDismiss={() => setLoginPrompt(false)}
          actions={
            <a href="/auth?next=/fanplan" className="app-toast-link">
              Log in
            </a>
          }
        />
      ) : null}
      {errorToast ? <AppToast message={errorToast} onDismiss={() => setErrorToast(null)} /> : null}

      <header className="md-glass md-glass-hero fanplan-panel overflow-hidden p-6 sm:p-8">
        <div className="md-glass-content">
          <p className="fanplan-kicker">2026 Host Cities · US · Canada · Mexico</p>
          <h1 className="md-page-title">Travel Planner</h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-app-muted">
            Build a multi-city route from the real openfootball schedule for your followed teams.
            Ticket costs and travel times are labeled estimates, not live prices or schedules.
          </p>
        </div>
      </header>

      <FanPlanControls
        teams={teams}
        selected={selected}
        maxCities={maxCities}
        budget={budget}
        onToggleTeam={toggleTeam}
        onMaxCitiesChange={setMaxCities}
        onBudgetChange={setBudget}
        onGenerate={generate}
      />

      {plan ? (
        <>
          <section className="md-glass fanplan-panel p-6 sm:p-8">
            <div className="md-glass-content space-y-8">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="fanplan-kicker">Step 2</p>
                  <h2 className="md-section-title text-champagne">Your plan</h2>
                </div>
                {plan.stops.length > 0 ? (
                  <button
                    type="button"
                    className="md-btn-secondary"
                    onClick={exportPdf}
                    disabled={exporting}
                  >
                    {exporting ? "Exporting…" : "Export itinerary (PDF)"}
                  </button>
                ) : null}
              </div>

              {plan.stops.length === 0 ? (
                <p className="text-sm text-app-muted">No stops fit your teams and constraints.</p>
              ) : (
                <>
                  <FanPlanStatCards
                    ticketLow={plan.total_ticket_cost_low_usd}
                    ticketHigh={plan.total_ticket_cost_high_usd}
                    travelHours={plan.total_travel_hours ?? 0}
                    travelKm={plan.total_travel_km ?? 0}
                    matchCount={plan.stops.length}
                  />
                  <FanPlanTimeline stops={plan.stops} zone={zone} />
                </>
              )}

              <FanPlanSkipped notes={skippedNotes} />
              <FanPlanInfoNotes notes={infoNotes} />

              <p className="fanplan-disclaimer">{plan.disclaimer}</p>
            </div>
          </section>

          {plan.stops.length > 0 ? (
            <div ref={mapRef}>
              <FanPlanMap stops={plan.stops} zone={zone} />
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
