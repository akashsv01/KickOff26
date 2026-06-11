/** Knockout bracket slot resolution and pick propagation helpers. */

export const ROUND_ORDER = ["r32", "r16", "qf", "sf", "final"] as const;
export type RoundId = (typeof ROUND_ORDER)[number];

/** Vertical space units per match (r32 = 1 unit). */
export const ROUND_HEIGHT_UNITS: Record<RoundId, number> = {
  r32: 1,
  r16: 2,
  qf: 4,
  sf: 8,
  final: 16,
};

/** Vertical pixels per r32 slot - must fit a two-team matchup box without overlap. */
export const MATCH_UNIT_PX = 96;

export function parseSlotId(slotId: string): { roundId: RoundId; index: number } | null {
  const m = slotId.match(/^(r32|r16|qf|sf|final)-(\d+)$/);
  if (!m) return null;
  return { roundId: m[1] as RoundId, index: parseInt(m[2], 10) - 1 };
}

export function slotCenterY(roundId: RoundId, index: number): number {
  const units = ROUND_HEIGHT_UNITS[roundId];
  const slotTop = index * units * MATCH_UNIT_PX;
  return slotTop + (units * MATCH_UNIT_PX) / 2;
}

export function descendantPickSlots(slotId: string): string[] {
  const parsed = parseSlotId(slotId);
  if (!parsed) return [];
  const out: string[] = [];
  let { roundId, index } = parsed;
  const startRi = ROUND_ORDER.indexOf(roundId);
  for (let ri = startRi + 1; ri < ROUND_ORDER.length; ri++) {
    const nextRound = ROUND_ORDER[ri];
    index = Math.floor(index / 2);
    out.push(`${nextRound}-${index + 1}`);
  }
  return out;
}

export function feederSlotIds(roundId: RoundId, matchIndex: number): [string, string] | null {
  const ri = ROUND_ORDER.indexOf(roundId);
  if (ri <= 0) return null;
  const prev = ROUND_ORDER[ri - 1];
  return [`${prev}-${matchIndex * 2 + 1}`, `${prev}-${matchIndex * 2 + 2}`];
}

export type MatchupSide =
  | { kind: "team"; code: string }
  | { kind: "placeholder"; label: string };

export function resolveMatchupSides(
  roundId: RoundId,
  matchIndex: number,
  picks: Record<string, string>,
  slotTeams: Record<string, string>
): [MatchupSide, MatchupSide] {
  if (roundId === "r32") {
    const slotId = `r32-${matchIndex + 1}`;
    const a = slotTeams[`${slotId}:a`];
    const b = slotTeams[`${slotId}:b`];
    return [
      a ? { kind: "team", code: a } : { kind: "placeholder", label: "TBD" },
      b ? { kind: "team", code: b } : { kind: "placeholder", label: "TBD" },
    ];
  }

  const feeders = feederSlotIds(roundId, matchIndex);
  if (!feeders) {
    return [
      { kind: "placeholder", label: "TBD" },
      { kind: "placeholder", label: "TBD" },
    ];
  }

  const [feedA, feedB] = feeders;
  const winnerA = picks[feedA];
  const winnerB = picks[feedB];

  const labelFor = (slot: string) => {
    const p = parseSlotId(slot);
    return p ? `Winner of M${p.index + 1}` : "TBD";
  };

  return [
    winnerA ? { kind: "team", code: winnerA } : { kind: "placeholder", label: labelFor(feedA) },
    winnerB ? { kind: "team", code: winnerB } : { kind: "placeholder", label: labelFor(feedB) },
  ];
}

export function applyKnockoutPick(
  picks: Record<string, string>,
  slotId: string,
  code: string
): Record<string, string> {
  const prev = picks[slotId];
  if (prev === code) return picks;
  const next = { ...picks, [slotId]: code };
  for (const downstream of descendantPickSlots(slotId)) {
    delete next[downstream];
  }
  return next;
}
