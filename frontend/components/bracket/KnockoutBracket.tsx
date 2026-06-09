"use client";

import { TeamFlag } from "@/components/TeamFlag";
import {
  MATCH_UNIT_PX,
  ROUND_HEIGHT_UNITS,
  ROUND_ORDER,
  type MatchupSide,
  type RoundId,
  resolveMatchupSides,
  slotCenterY,
} from "@/lib/knockoutBracket";

type KnockoutRound = {
  id: string;
  label: string;
  slots: { slot: string; label: string }[];
};

function MatchupBox({
  slotId,
  sideA,
  sideB,
  winnerCode,
  onPick,
  isFinal,
}: {
  slotId: string;
  sideA: MatchupSide;
  sideB: MatchupSide;
  winnerCode?: string;
  onPick: (slotId: string, code: string) => void;
  isFinal?: boolean;
}) {
  const canPick = sideA.kind === "team" && sideB.kind === "team";

  function TeamLine({ side }: { side: MatchupSide }) {
    if (side.kind === "placeholder") {
      return (
        <div className="flex w-full items-center gap-2 border-b border-app-faint/20 px-3 py-2 text-left last:border-0">
          <span className="h-3 w-4 shrink-0 rounded-sm bg-app-faint/15" aria-hidden />
          <span className="truncate text-xs font-medium italic text-app-faint">{side.label}</span>
        </div>
      );
    }

    const selected = winnerCode === side.code;
    const isChampion = isFinal && selected;

    return (
      <button
        type="button"
        disabled={!canPick}
        onClick={() => onPick(slotId, side.code)}
        className={`flex w-full items-center justify-between gap-2 border-b border-app-faint/20 px-3 py-2 text-left transition last:border-0 ${
          canPick ? "cursor-pointer hover:bg-app/10" : "cursor-default opacity-70"
        } ${
          selected
            ? isChampion
              ? "bg-champagne/25 text-champagne ring-1 ring-inset ring-champagne/50"
              : "bg-champagne/15 text-champagne"
            : ""
        }`}
      >
        <span className="inline-flex min-w-0 items-center gap-2">
          <TeamFlag code={side.code} size="xs" className="shadow-none" />
          <span className="font-bold tracking-wide text-app">{side.code}</span>
        </span>
        {selected ? (
          <span className="shrink-0 text-[10px] font-bold uppercase text-champagne">
            {isChampion ? "Champion" : "Adv"}
          </span>
        ) : null}
      </button>
    );
  }

  return (
    <div
      className={`md-glass w-[148px] shrink-0 overflow-hidden border shadow-[var(--glass-shadow)] ${
        isFinal && winnerCode ? "border-champagne/60" : "border-app-faint/35"
      }`}
    >
      <TeamLine side={sideA} />
      <TeamLine side={sideB} />
    </div>
  );
}

function ConnectorSvg({
  fromRound,
  toRound,
  fromCount,
}: {
  fromRound: RoundId;
  toRound: RoundId;
  fromCount: number;
}) {
  const toCount = fromCount / 2;
  const fromUnits = ROUND_HEIGHT_UNITS[fromRound];
  const totalHeight = fromCount * fromUnits * MATCH_UNIT_PX;
  const midX = 20;

  const paths: string[] = [];
  for (let i = 0; i < toCount; i++) {
    const y1 = slotCenterY(fromRound, i * 2);
    const y2 = slotCenterY(fromRound, i * 2 + 1);
    const yMid = slotCenterY(toRound, i);
    paths.push(`M 0 ${y1} H ${midX} V ${yMid} H 40`);
    paths.push(`M 0 ${y2} H ${midX} V ${yMid}`);
  }

  return (
    <svg
      className="bracket-connector-svg shrink-0"
      width={40}
      height={totalHeight}
      viewBox={`0 0 40 ${totalHeight}`}
      aria-hidden
    >
      {paths.map((d, i) => (
        <path
          key={i}
          d={d}
          fill="none"
          stroke="var(--bracket-line)"
          strokeWidth={2}
          strokeLinejoin="round"
        />
      ))}
    </svg>
  );
}

export function KnockoutBracket({
  rounds,
  picks,
  slotTeams,
  onPick,
}: {
  rounds: KnockoutRound[];
  picks: Record<string, string>;
  slotTeams: Record<string, string>;
  onPick: (slotId: string, code: string) => void;
}) {
  const orderedRounds = ROUND_ORDER.map((id) => rounds.find((r) => r.id === id)).filter(
    Boolean
  ) as KnockoutRound[];

  const totalHeight = 16 * MATCH_UNIT_PX;

  return (
    <div className="bracket-tree -mx-2 overflow-x-auto pb-4">
      <div className="flex min-w-max items-start px-2" style={{ minHeight: totalHeight }}>
        {orderedRounds.map((round, roundIdx) => {
          const roundId = round.id as RoundId;
          const units = ROUND_HEIGHT_UNITS[roundId];

          return (
            <div key={round.id} className="flex shrink-0 items-start">
              {roundIdx > 0 ? (
                <ConnectorSvg
                  fromRound={orderedRounds[roundIdx - 1].id as RoundId}
                  toRound={roundId}
                  fromCount={orderedRounds[roundIdx - 1].slots.length}
                />
              ) : null}

              <div className="flex shrink-0 flex-col" style={{ minHeight: totalHeight }}>
                <h3 className="mb-3 text-center text-xs font-bold uppercase tracking-widest text-champagne">
                  {round.label}
                </h3>
                <div className="relative flex flex-1 flex-col" style={{ minHeight: totalHeight - 28 }}>
                  {round.slots.map((slot, i) => {
                    const [sideA, sideB] = resolveMatchupSides(
                      roundId,
                      i,
                      picks,
                      slotTeams
                    );
                    return (
                      <div
                        key={slot.slot}
                        className="flex shrink-0 items-center justify-center"
                        style={{ height: units * MATCH_UNIT_PX, minHeight: units * MATCH_UNIT_PX }}
                      >
                        <MatchupBox
                          slotId={slot.slot}
                          sideA={sideA}
                          sideB={sideB}
                          winnerCode={picks[slot.slot]}
                          onPick={onPick}
                          isFinal={roundId === "final"}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
