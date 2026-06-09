/**
 * Official FIFA World Cup 2026 Round of 32 seeding.
 *
 * Match layout from tournament schedule (matches 73–88). Each slot is either:
 * - a fixed group finisher (1A = winner of A, 2B = runner-up of B), or
 * - a third-place berth with an eligible-group list (e.g. 3A/B/C/D/F).
 *
 * The eight advancing third-placed teams are assigned to berths via backtracking
 * so each third plays a group winner from a different group and every berth is filled.
 * (FIFA publishes 495 combination-specific tables in Annex C; this satisfies the
 * same structural constraints: unique teams, no same-group R32 ties, thirds vs winners.)
 */

import type { StandingRow } from "./bracketGroups";

type FixedSide = { kind: "fixed"; position: string };
type ThirdSide = { kind: "third"; eligibleGroups: string[]; opponentGroup: string };
type SideDef = FixedSide | ThirdSide;

function fixed(position: string): FixedSide {
  return { kind: "fixed", position };
}

function third(eligibleGroups: string[], opponentGroup: string): ThirdSide {
  return { kind: "third", eligibleGroups, opponentGroup };
}

/** Official R32 template — index 0 = bracket slot r32-1 (WC match 73). */
export const R32_OFFICIAL_TEMPLATE: readonly [SideDef, SideDef][] = [
  [fixed("2A"), fixed("2B")],
  [fixed("1E"), third(["A", "B", "C", "D", "F"], "E")],
  [fixed("1F"), fixed("2C")],
  [fixed("1C"), fixed("2F")],
  [fixed("1I"), third(["C", "D", "F", "G", "H"], "I")],
  [fixed("2E"), fixed("2I")],
  [fixed("1A"), third(["C", "E", "F", "H", "I"], "A")],
  [fixed("1L"), third(["E", "H", "I", "J", "K"], "L")],
  [fixed("1D"), third(["B", "E", "F", "I", "J"], "D")],
  [fixed("1G"), third(["A", "E", "H", "I", "J"], "G")],
  [fixed("2K"), fixed("2L")],
  [fixed("1H"), fixed("2J")],
  [fixed("1B"), third(["E", "F", "G", "I", "J"], "B")],
  [fixed("1J"), fixed("2H")],
  [fixed("1K"), third(["D", "E", "I", "J", "L"], "K")],
  [fixed("2D"), fixed("2G")],
];

export type ThirdAdvancer = { group: string; code: string };

export function thirdAdvancersWithGroups(
  standingsByGroup: Record<string, StandingRow[]>,
  thirdAdvancerCodes: string[]
): ThirdAdvancer[] {
  const codeSet = new Set(thirdAdvancerCodes);
  const out: ThirdAdvancer[] = [];
  for (const [group, rows] of Object.entries(standingsByGroup)) {
    const third = rows[2];
    if (third && codeSet.has(third.code)) {
      out.push({ group, code: third.code });
    }
  }
  return out.sort((a, b) => a.group.localeCompare(b.group));
}

export function qualifierTeamCodes(
  standingsByGroup: Record<string, StandingRow[]>,
  thirdAdvancers: string[]
): Set<string> {
  const codes = new Set<string>();
  for (const rows of Object.values(standingsByGroup)) {
    if (rows[0]?.code) codes.add(rows[0].code);
    if (rows[1]?.code) codes.add(rows[1].code);
  }
  for (const code of thirdAdvancers) codes.add(code);
  return codes;
}

function teamToGroupMap(standingsByGroup: Record<string, StandingRow[]>): Map<string, string> {
  const map = new Map<string, string>();
  for (const [group, rows] of Object.entries(standingsByGroup)) {
    for (const row of rows) map.set(row.code, group);
  }
  return map;
}

function resolveFixedSide(
  side: FixedSide,
  standingsByGroup: Record<string, StandingRow[]>
): string | null {
  const group = side.position[1];
  const rank = side.position[0] === "1" ? 0 : 1;
  return standingsByGroup[group]?.[rank]?.code ?? null;
}

type ThirdSlotDef = { matchIndex: number; eligibleGroups: string[] };

/**
 * Assign each advancing third-placed team to exactly one official third berth.
 * Slots are tried most-constrained-first for reliable backtracking.
 */
export function assignThirdPlaceBerths(
  advancingThirds: ThirdAdvancer[],
  slotDefs: ThirdSlotDef[]
): Record<number, string> | null {
  const ordered = [...slotDefs].sort(
    (a, b) => a.eligibleGroups.length - b.eligibleGroups.length
  );
  const assignment: Record<number, string> = {};

  function backtrack(slotIdx: number, remaining: ThirdAdvancer[]): boolean {
    if (slotIdx >= ordered.length) return true;
    const slot = ordered[slotIdx];
    for (let i = 0; i < remaining.length; i++) {
      const team = remaining[i];
      if (!slot.eligibleGroups.includes(team.group)) continue;
      assignment[slot.matchIndex] = team.code;
      const next = remaining.filter((_, j) => j !== i);
      if (backtrack(slotIdx + 1, next)) return true;
    }
    return false;
  }

  if (!backtrack(0, advancingThirds)) return null;
  return assignment;
}

export function buildR32Pairings(
  standingsByGroup: Record<string, StandingRow[]>,
  thirdAdvancerCodes: string[]
): [string, string][] {
  const advancingThirds = thirdAdvancersWithGroups(standingsByGroup, thirdAdvancerCodes);
  if (advancingThirds.length !== 8) {
    console.error("[R32 seeding] Expected 8 third-place advancers, got", advancingThirds.length);
    return [];
  }

  const thirdSlotDefs: ThirdSlotDef[] = [];
  R32_OFFICIAL_TEMPLATE.forEach((match, matchIndex) => {
    for (const side of match) {
      if (side.kind === "third") {
        thirdSlotDefs.push({ matchIndex, eligibleGroups: side.eligibleGroups });
      }
    }
  });

  const thirdByMatch = assignThirdPlaceBerths(advancingThirds, thirdSlotDefs);
  if (!thirdByMatch) {
    console.error(
      "[R32 seeding] Could not assign third-place teams to official berths",
      advancingThirds.map((t) => t.group)
    );
    return [];
  }

  const pairings: [string, string][] = [];
  for (let matchIndex = 0; matchIndex < R32_OFFICIAL_TEMPLATE.length; matchIndex++) {
    const [sideA, sideB] = R32_OFFICIAL_TEMPLATE[matchIndex];
    const codeA =
      sideA.kind === "fixed"
        ? resolveFixedSide(sideA, standingsByGroup)
        : thirdByMatch[matchIndex] ?? null;
    const codeB =
      sideB.kind === "fixed"
        ? resolveFixedSide(sideB, standingsByGroup)
        : thirdByMatch[matchIndex] ?? null;

    if (!codeA || !codeB) {
      console.error("[R32 seeding] Missing team for match", matchIndex + 1, { codeA, codeB });
      return [];
    }
    pairings.push([codeA, codeB]);
  }

  return pairings;
}

export function buildR32SlotTeams(pairings: [string, string][]): Record<string, string> {
  const slotTeams: Record<string, string> = {};
  pairings.forEach(([home, away], i) => {
    const slot = `r32-${i + 1}`;
    slotTeams[`${slot}:a`] = home;
    slotTeams[`${slot}:b`] = away;
  });
  return slotTeams;
}

/** Validate seeded R32: 32 unique teams matching the qualifier set, no same-group ties. */
export function validateR32SlotTeams(
  slotTeams: Record<string, string>,
  standingsByGroup: Record<string, StandingRow[]>,
  thirdAdvancers: string[]
): boolean {
  const codes = Object.values(slotTeams);
  if (codes.length !== 32) {
    console.error("[R32 seeding] Expected 32 slot entries, got", codes.length);
    return false;
  }

  const unique = new Set(codes);
  if (unique.size !== 32) {
    console.error("[R32 seeding] Duplicate teams in R32:", codes.length - unique.size, "duplicates");
    return false;
  }

  const expected = qualifierTeamCodes(standingsByGroup, thirdAdvancers);
  if (expected.size !== 32) {
    console.error("[R32 seeding] Qualifier set size is not 32:", expected.size);
    return false;
  }

  for (const code of unique) {
    if (!expected.has(code)) {
      console.error("[R32 seeding] Team not in qualifier set:", code);
      return false;
    }
  }
  for (const code of expected) {
    if (!unique.has(code)) {
      console.error("[R32 seeding] Qualifier missing from R32:", code);
      return false;
    }
  }

  const teamGroup = teamToGroupMap(standingsByGroup);
  for (let i = 1; i <= 16; i++) {
    const a = slotTeams[`r32-${i}:a`];
    const b = slotTeams[`r32-${i}:b`];
    if (a && b && teamGroup.get(a) === teamGroup.get(b)) {
      console.error("[R32 seeding] Same-group matchup in r32-" + i, teamGroup.get(a));
      return false;
    }
  }

  return true;
}

export function seedR32FromStandings(
  standingsByGroup: Record<string, StandingRow[]>,
  thirdAdvancers: string[]
): Record<string, string> {
  const pairings = buildR32Pairings(standingsByGroup, thirdAdvancers);
  if (pairings.length !== 16) return {};
  const slotTeams = buildR32SlotTeams(pairings);
  if (!validateR32SlotTeams(slotTeams, standingsByGroup, thirdAdvancers)) {
    return {};
  }
  return slotTeams;
}
