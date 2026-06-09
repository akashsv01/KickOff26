/** Group-stage standings, simulation, and knockout seeding for Bracket Predictor. */

export type MatchOdds = { home: number; draw: number; away: number };

export type MatchResult = { home_score: number; away_score: number };

export type StandingRow = {
  code: string;
  name: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  gd: number;
  points: number;
  rank: number;
};

export type GroupFixture = {
  id: number;
  home: { code: string; name: string };
  away: { code: string; name: string };
};

export type GroupTeam = { id: number; name: string; code: string };

export type GroupResults = Record<number, MatchResult | null>;

function emptyRow(code: string, name: string): StandingRow {
  return {
    code,
    name,
    played: 0,
    won: 0,
    drawn: 0,
    lost: 0,
    gf: 0,
    ga: 0,
    gd: 0,
    points: 0,
    rank: 0,
  };
}

function standingSortKey(row: StandingRow): [number, number, number] {
  return [row.points, row.gd, row.gf];
}

export function applyMatchResult(
  home: StandingRow,
  away: StandingRow,
  hs: number,
  aws: number
): void {
  home.played += 1;
  away.played += 1;
  home.gf += hs;
  home.ga += aws;
  away.gf += aws;
  away.ga += hs;
  if (hs > aws) {
    home.won += 1;
    home.points += 3;
    away.lost += 1;
  } else if (hs < aws) {
    away.won += 1;
    away.points += 3;
    home.lost += 1;
  } else {
    home.drawn += 1;
    away.drawn += 1;
    home.points += 1;
    away.points += 1;
  }
}

export function computeGroupStandings(
  teams: GroupTeam[],
  fixtures: GroupFixture[],
  results: GroupResults
): StandingRow[] {
  const rows = Object.fromEntries(teams.map((t) => [t.code, emptyRow(t.code, t.name)]));

  for (const fixture of fixtures) {
    const result = results[fixture.id];
    if (!result) continue;
    const home = rows[fixture.home.code];
    const away = rows[fixture.away.code];
    if (!home || !away) continue;
    applyMatchResult(home, away, result.home_score, result.away_score);
  }

  const sorted = Object.values(rows).sort((a, b) => {
    const ka = standingSortKey(a);
    const kb = standingSortKey(b);
    for (let i = 0; i < 3; i++) {
      if (kb[i] !== ka[i]) return kb[i] - ka[i];
    }
    return 0;
  });

  return sorted.map((row, i) => ({
    ...row,
    rank: i + 1,
    gd: row.gf - row.ga,
  }));
}

export function computeAllStandings(
  groups: Record<string, GroupTeam[]>,
  fixturesByGroup: Record<string, GroupFixture[]>,
  results: GroupResults
): Record<string, StandingRow[]> {
  const out: Record<string, StandingRow[]> = {};
  for (const [group, teams] of Object.entries(groups)) {
    out[group] = computeGroupStandings(teams, fixturesByGroup[group] || [], results);
  }
  return out;
}

export function rankThirdPlaced(standingsByGroup: Record<string, StandingRow[]>): string[] {
  const thirds: StandingRow[] = [];
  for (const rows of Object.values(standingsByGroup)) {
    if (rows.length >= 3) thirds.push(rows[2]);
  }
  thirds.sort((a, b) => {
    const ka = standingSortKey(a);
    const kb = standingSortKey(b);
    for (let i = 0; i < 3; i++) {
      if (kb[i] !== ka[i]) return kb[i] - ka[i];
    }
    return 0;
  });
  return thirds.slice(0, 8).map((r) => r.code);
}

export {
  buildR32Pairings,
  buildR32SlotTeams,
  seedR32FromStandings,
  validateR32SlotTeams,
} from "./r32Seeding";

export function fixtureOddsKey(group: string, home: string, away: string): string {
  return `${group}:${home}_vs_${away}`;
}

export function countDecidedResults(
  fixturesByGroup: Record<string, GroupFixture[]>,
  results: GroupResults
): { decided: number; total: number } {
  const all = Object.values(fixturesByGroup).flat();
  const decided = all.filter((f) => results[f.id] != null).length;
  return { decided, total: all.length };
}

export function biasUpsetOdds(odds: MatchOdds): MatchOdds {
  const favorite = odds.home >= odds.away ? "home" : "away";
  const underdog = favorite === "home" ? "away" : "home";
  const boosted = { ...odds };
  boosted[underdog] *= 1.45;
  boosted[favorite] *= 0.72;
  boosted.draw *= 1.08;
  const sum = boosted.home + boosted.draw + boosted.away;
  return {
    home: boosted.home / sum,
    draw: boosted.draw / sum,
    away: boosted.away / sum,
  };
}

export function sampleOutcome(odds: MatchOdds, upsets: boolean): "home" | "draw" | "away" {
  const probs = upsets ? biasUpsetOdds(odds) : odds;
  const r = Math.random();
  if (r < probs.home) return "home";
  if (r < probs.home + probs.draw) return "draw";
  return "away";
}

export function scoresFromOutcome(outcome: "home" | "draw" | "away"): MatchResult {
  if (outcome === "draw") {
    const goals = Math.floor(Math.random() * 3);
    return { home_score: goals, away_score: goals };
  }
  if (outcome === "home") {
    const hg = 1 + Math.floor(Math.random() * 3);
    const ag = Math.floor(Math.random() * hg);
    return { home_score: hg, away_score: ag };
  }
  const ag = 1 + Math.floor(Math.random() * 3);
  const hg = Math.floor(Math.random() * ag);
  return { home_score: hg, away_score: ag };
}

export function quickResult(outcome: "home" | "draw" | "away"): MatchResult {
  if (outcome === "home") return { home_score: 2, away_score: 1 };
  if (outcome === "away") return { home_score: 1, away_score: 2 };
  return { home_score: 1, away_score: 1 };
}

export function simulateFixtureResult(
  group: string,
  fixture: GroupFixture,
  matchOdds: Record<string, MatchOdds>,
  upsets: boolean
): MatchResult {
  const key = fixtureOddsKey(group, fixture.home.code, fixture.away.code);
  const odds = matchOdds[key] ?? { home: 0.33, draw: 0.34, away: 0.33 };
  return scoresFromOutcome(sampleOutcome(odds, upsets));
}

export function simulateGroupFixtures(
  group: string,
  fixtures: GroupFixture[],
  matchOdds: Record<string, MatchOdds>,
  upsets: boolean,
  existing: GroupResults,
  onlyUndecided: boolean
): GroupResults {
  const next = { ...existing };
  for (const fixture of fixtures) {
    if (onlyUndecided && next[fixture.id] != null) continue;
    next[fixture.id] = simulateFixtureResult(group, fixture, matchOdds, upsets);
  }
  return next;
}

export function simulateAllGroups(
  fixturesByGroup: Record<string, GroupFixture[]>,
  matchOdds: Record<string, MatchOdds>,
  upsets: boolean,
  existing: GroupResults,
  onlyUndecided: boolean
): GroupResults {
  let next = { ...existing };
  for (const [group, fixtures] of Object.entries(fixturesByGroup)) {
    next = simulateGroupFixtures(group, fixtures, matchOdds, upsets, next, onlyUndecided);
  }
  return next;
}

export function normalizeGroupResults(raw: Record<string, MatchResult> | undefined): GroupResults {
  if (!raw) return {};
  const out: GroupResults = {};
  for (const [key, value] of Object.entries(raw)) {
    out[Number(key)] = value;
  }
  return out;
}

export function serializeGroupResults(results: GroupResults): Record<string, MatchResult> {
  const out: Record<string, MatchResult> = {};
  for (const [id, value] of Object.entries(results)) {
    if (value != null) out[String(id)] = value;
  }
  return out;
}
