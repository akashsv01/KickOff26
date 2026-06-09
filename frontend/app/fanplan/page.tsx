"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { AppToast } from "@/components/AppToast";
import { FanPlanControls } from "@/components/fanplan/FanPlanControls";
import { FanPlanInfoNotes, FanPlanSkipped } from "@/components/fanplan/FanPlanSkipped";
import { FanPlanStatCards } from "@/components/fanplan/FanPlanStatCards";
import { FanPlanTimeline } from "@/components/fanplan/FanPlanTimeline";
import { normalizeItinerary, type Itinerary } from "@/lib/fanplan";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const FanPlanMap = dynamic(() => import("@/components/FanPlanMap"), { ssr: false });

type Team = { id: number; name: string; code: string };

export default function FanPlanPage() {
  const { user } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [plan, setPlan] = useState<Itinerary | null>(null);
  const [maxCities, setMaxCities] = useState(5);
  const [budget, setBudget] = useState<number | "">("");
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [errorToast, setErrorToast] = useState<string | null>(null);

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
          <h1 className="md-page-title">FanPlan Itinerary</h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-app-muted">
            Build a multi-city route from the real openfootball schedule for your followed teams.
            Ticket costs and travel times are labeled estimates — not live prices or schedules.
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
              <div>
                <p className="fanplan-kicker">Step 2</p>
                <h2 className="md-section-title text-champagne">Your plan</h2>
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
                  <FanPlanTimeline stops={plan.stops} />
                </>
              )}

              <FanPlanSkipped notes={skippedNotes} />
              <FanPlanInfoNotes notes={infoNotes} />

              <p className="fanplan-disclaimer">{plan.disclaimer}</p>
            </div>
          </section>

          {plan.stops.length > 0 ? <FanPlanMap stops={plan.stops} /> : null}
        </>
      ) : null}
    </div>
  );
}
