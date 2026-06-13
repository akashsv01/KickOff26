"use client";

import { TeamFlag } from "@/components/TeamFlag";
import type { Match, MatchEvent } from "@/lib/matchday";

function eventIcon(type: string, detail?: string): string {
  switch (type) {
    case "goal":
      return "⚽";
    case "penalty":
      return detail === "missed" ? "❌" : "⚽";
    case "red_card":
      return "🟥";
    case "yellow_card":
      return "🟨";
    case "substitution":
      return "🔄";
    case "var":
      return "📺";
    default:
      return "•";
  }
}

function eventTitle(e: MatchEvent): string {
  switch (e.type) {
    case "goal":
      return "Goal";
    case "penalty":
      return e.detail === "missed" ? "Penalty missed" : "Penalty goal";
    case "red_card":
      return "Red card";
    case "yellow_card":
      return "Yellow card";
    case "substitution":
      return "Substitution";
    case "var":
      return `VAR${e.detail ? `: ${e.detail}` : ""}`;
    default:
      return e.type;
  }
}

/**
 * Vertical themed match timeline: central spine, minute bubbles, and event
 * cards alternating by side (home left / away right) with team-color accents.
 * Caps with "Match Started" at 0' and "Full Time" when finished.
 *
 * Consumes the structured events from the backend: a null minute renders a plain
 * node (no "0'" bubble) and an empty/absent player renders a neutral "<Team> goal".
 */
export function MatchTimeline({
  match,
  events,
  isFinished,
}: {
  match: Match;
  events: MatchEvent[];
  isFinished: boolean;
}) {
  return (
    <ol className="md-tl" aria-label="Match timeline">
      <li className="md-tl-cap">
        <span>● Match Started · 0&apos;</span>
      </li>

      {events.map((e, i) => {
        const side = e.team === "away" ? "away" : "home";
        const team = side === "away" ? match.away_team : match.home_team;
        const player = (e.player ?? "").trim();
        const isGoalish = e.type === "goal" || e.type === "penalty";
        const subject =
          player || (isGoalish ? `${team?.name ?? team?.code ?? "Team"} goal` : "");
        const hasMinute = typeof e.minute === "number";
        const minuteLabel = hasMinute
          ? `${e.minute}${typeof e.added_time === "number" && e.added_time > 0 ? `+${e.added_time}` : ""}'`
          : "";

        return (
          <li key={i} className={`md-tl-row md-tl-${side}`}>
            <div className="md-tl-card">
              <div className="md-tl-team">
                <TeamFlag code={team?.code ?? "???"} size="sm" />
                <span>{team?.code ?? "???"}</span>
              </div>
              <div className="md-tl-title">
                <span aria-hidden="true">{eventIcon(e.type, e.detail)}</span> {eventTitle(e)}
              </div>
              {subject && <div className="md-tl-player">{subject}</div>}
            </div>
            <span className={`md-tl-bubble${hasMinute ? "" : " md-tl-bubble-empty"}`}>
              {minuteLabel}
            </span>
          </li>
        );
      })}

      {isFinished && (
        <li className="md-tl-cap">
          <span>
            ● Full Time · {match.home_score ?? 0}-{match.away_score ?? 0}
          </span>
        </li>
      )}
    </ol>
  );
}
