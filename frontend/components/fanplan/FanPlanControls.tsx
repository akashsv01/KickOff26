"use client";

import { TeamFlag } from "@/components/TeamFlag";

type Team = { id: number; name: string; code: string };

type Props = {
  teams: Team[];
  selected: number[];
  maxCities: number;
  budget: number | "";
  onToggleTeam: (id: number) => void;
  onMaxCitiesChange: (n: number) => void;
  onBudgetChange: (v: number | "") => void;
  onGenerate: () => void;
};

export function FanPlanControls({
  teams,
  selected,
  maxCities,
  budget,
  onToggleTeam,
  onMaxCitiesChange,
  onBudgetChange,
  onGenerate,
}: Props) {
  return (
    <div className="md-glass fanplan-panel overflow-hidden p-6 sm:p-7">
      <div className="md-glass-content space-y-6">
        <div>
          <p className="fanplan-kicker">Step 1</p>
          <h2 className="md-section-title">Select teams to follow</h2>
          <p className="mt-1 text-sm text-app-muted">
            Choose the nations you want to chase across host cities.
          </p>
        </div>

        <div className="fanplan-team-grid">
          {teams.map((t) => {
            const active = selected.includes(t.id);
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => onToggleTeam(t.id)}
                className={`fanplan-team-chip ${active ? "fanplan-team-chip-active" : ""}`}
                aria-pressed={active}
              >
                <TeamFlag code={t.code} size="sm" className="shadow-none" />
                <span className="font-bold tracking-tight">{t.code}</span>
              </button>
            );
          })}
        </div>

        <div className="fanplan-controls-row">
          <div className="fanplan-field">
            <label htmlFor="fanplan-max-cities" className="fanplan-field-label">
              Max cities
            </label>
            <input
              id="fanplan-max-cities"
              type="number"
              min={1}
              max={16}
              value={maxCities}
              onChange={(e) => onMaxCitiesChange(Number(e.target.value))}
              className="fanplan-input"
            />
          </div>
          <div className="fanplan-field fanplan-field-wide">
            <label htmlFor="fanplan-budget" className="fanplan-field-label">
              Budget (USD, optional)
            </label>
            <input
              id="fanplan-budget"
              type="number"
              min={0}
              value={budget}
              onChange={(e) => onBudgetChange(e.target.value ? Number(e.target.value) : "")}
              className="fanplan-input"
              placeholder="Ticket est. high end"
            />
            <p className="fanplan-field-hint">
              Compared against the high end of estimated ticket ranges.
            </p>
          </div>
          <div className="fanplan-generate-wrap">
            <button type="button" className="md-btn-primary fanplan-generate-btn" onClick={onGenerate}>
              Generate itinerary
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
