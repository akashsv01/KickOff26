"use client";

import { InfoTooltip } from "@/components/InfoTooltip";
import { TeamFlag } from "@/components/TeamFlag";

const PATH_FREQUENCY_TOOLTIP =
  "This is the single most common complete bracket across all simulations. Any one exact full bracket is rare because it combines the outcomes of many matches - so even the most likely complete path appears in only a small fraction of runs. Individual round-by-round predictions are far more probable than the full bracket as a whole.";

type PathRound = {
  id: string;
  label: string;
  winners: string[];
};

export type MostLikelyPathData = {
  champion: string;
  occurrences?: number;
  frequency_pct?: number;
  methodology?: string;
  rounds: PathRound[];
  final: { teams: string[]; champion: string };
};

export function MostLikelyPath({ path }: { path: MostLikelyPathData | null }) {
  if (!path?.champion) {
    return <p className="text-sm text-app-muted">Run a simulation to see the most likely knockout path.</p>;
  }

  return (
    <div className="sim-path mt-3 space-y-4">
      <p className="mt-0 flex flex-wrap items-center gap-x-1 text-xs text-app-muted">
        <span>
          Modal full knockout outcome
          {path.frequency_pct != null ? (
            <>
              {" "}
              · seen in{" "}
              <span className="font-semibold text-app">{path.frequency_pct.toFixed(1)}%</span> of runs
            </>
          ) : null}
        </span>
        <InfoTooltip
          label="About the seen-in percentage"
          text={PATH_FREQUENCY_TOOLTIP}
        />
      </p>
      {"methodology" in path && path.methodology ? (
        <p className="text-xs text-app-muted">{String(path.methodology)}</p>
      ) : null}

      {path.rounds.map((round) => (
        <section key={round.id}>
          <h4 className="sim-path-round-title">{round.label}</h4>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {round.winners.map((code, i) => (
              <TeamChip key={`${round.id}-${code}-${i}`} code={code} />
            ))}
          </div>
        </section>
      ))}

      <section>
        <h4 className="sim-path-round-title">Final</h4>
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          {path.final.teams.map((code) => (
            <TeamChip
              key={`final-${code}`}
              code={code}
              highlight={code === path.final.champion}
              label={code === path.final.champion ? "Champion" : undefined}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

function TeamChip({
  code,
  highlight,
  label,
}: {
  code: string;
  highlight?: boolean;
  label?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-bold ${
        highlight
          ? "border-champagne/50 bg-champagne/15 text-app"
          : "border-app-faint/25 bg-app/5 text-app"
      }`}
    >
      <TeamFlag code={code} size="xs" className="shadow-none" />
      {code}
      {label ? (
        <span className="text-[10px] font-bold uppercase tracking-wide text-champagne">{label}</span>
      ) : null}
    </span>
  );
}
