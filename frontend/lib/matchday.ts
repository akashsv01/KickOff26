export type MatchTeam = {
  id: number;
  name: string;
  code: string;
  elo_rating?: number;
  group_letter?: string | null;
};

export type MatchEvent = {
  type: string;
  minute: number;
  team?: string;
  player?: string;
};

export type ModelContext = {
  home_elo: number;
  away_elo: number;
  favorite_code: string;
  summary: string;
  pre_match: { home: number; draw: number; away: number };
};

export type Match = {
  id: number;
  home_team: MatchTeam;
  away_team: MatchTeam;
  home_score: number | null;
  away_score: number | null;
  minute: number | null;
  status: string;
  win_prob_home: number | null;
  win_prob_draw: number | null;
  win_prob_away: number | null;
  city: string | null;
  venue?: string | null;
  kickoff_at?: string | null;
  local_date?: string | null;
  timezone?: string | null;
  stage?: string | null;
  group_letter?: string | null;
  country?: string | null;
  events?: MatchEvent[];
  model_context?: ModelContext;
  followed_team_id?: number;
  home_lineup?: LineupPlayer[];
  away_lineup?: LineupPlayer[];
  lineups?: {
    home: LineupSide;
    away: LineupSide;
  } | null;
};

export type LineupPlayer = {
  number: number;
  name: string;
  position: string;
  grid?: string;
};

export type LineupSide = {
  formation?: string | null;
  coach?: string | null;
  starting_xi: LineupPlayer[];
  bench: LineupPlayer[];
};

export type MatchDay = { date: string; match_count: number };

export type Team = {
  id: number;
  name: string;
  code: string;
  group_letter?: string | null;
  elo_rating?: number;
};

/** Eastern Time calendar day (official 2026 schedule) - never fall back to UTC kickoff slice. */
export function matchDateKey(match: Pick<Match, "local_date">): string | null {
  return match.local_date ?? null;
}

export function matchesForDay(matches: Match[], day: string): Match[] {
  return matches.filter((m) => matchDateKey(m) === day);
}

export function dayCountsFromMatches(matches: Match[]): MatchDay[] {
  const counts: Record<string, number> = {};
  for (const m of matches) {
    const key = matchDateKey(m);
    if (key) counts[key] = (counts[key] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([date, match_count]) => ({ date, match_count }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function formatKickoff(iso: string | null | undefined, opts?: Intl.DateTimeFormatOptions) {
  if (!iso) return "TBD";
  return new Date(iso).toLocaleString(undefined, opts ?? {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDayLabel(dateKey: string) {
  const d = new Date(dateKey + "T12:00:00");
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export const TOURNAMENT_WINDOW = { start: "2026-06-11", end: "2026-07-19" };

export function defaultMatchDay(dates: string[]): string {
  if (!dates.length) return "";
  const today = new Date().toISOString().slice(0, 10);
  const inWindow = today >= TOURNAMENT_WINDOW.start && today <= TOURNAMENT_WINDOW.end;
  if (inWindow && dates.includes(today)) return today;
  if (inWindow) {
    const future = dates.find((d) => d >= today);
    if (future) return future;
  }
  return dates[0];
}

export function sortDayMatches(matches: Match[]): Match[] {
  const live = matches.filter((m) => m.status === "live");
  const rest = matches.filter((m) => m.status !== "live");
  rest.sort((a, b) => (a.kickoff_at ?? "").localeCompare(b.kickoff_at ?? ""));
  return [...live, ...rest];
}

export function groupByKickoffSlot(matches: Match[]): Record<string, Match[]> {
  const groups: Record<string, Match[]> = {};
  for (const m of matches) {
    const slot = m.kickoff_at ? formatKickoff(m.kickoff_at, { hour: "2-digit", minute: "2-digit" }) : "TBD";
    const key = `Group ${m.group_letter ?? "?"} · ${slot}`;
    groups[key] = groups[key] ?? [];
    groups[key].push(m);
  }
  return groups;
}

/** Canonical detail route for a fixture. */
export function matchDetailHref(matchId: number): string {
  if (!Number.isFinite(matchId) || matchId <= 0) return "/matchday";
  return `/matchday/${matchId}`;
}

/** Imperative navigation helper (testable). */
export function navigateToMatchDetail(
  navigate: (href: string) => void,
  matchId: number
): void {
  navigate(matchDetailHref(matchId));
}

export type MatchAlertPayload = {
  type?: string;
  message?: string;
  match_id?: number;
  shift?: number;
};

export type MatchNotification = {
  id: string;
  type:
    | "goal"
    | "yellow_card"
    | "red_card"
    | "substitution"
    | "penalty"
    | "var"
    | "match_start"
    | "match_halftime"
    | "match_end"
    | "momentum";
  message: string;
  matchId?: number;
  at: Date;
  read: boolean;
};

export const PROB_SWING_THRESHOLD = 0.15;
export const NOTIFICATION_STORE_CAP = 20;
export const MAX_VISIBLE_NOTIFICATIONS = 8;

const MEANINGFUL_ALERT_TYPES = new Set([
  "goal_alert",
  "yellow_card_alert",
  "red_card_alert",
  "substitution_alert",
  "penalty_alert",
  "var_alert",
  "match_start_alert",
  "match_halftime_alert",
  "match_end_alert",
  "momentum_alert",
]);

/** Only surface free-tier supported alerts + ±15% probability swings. */
export function shouldShowAlert(data: MatchAlertPayload): boolean {
  const type = String(data.type ?? "");
  if (!MEANINGFUL_ALERT_TYPES.has(type)) return false;
  if (type === "momentum_alert") {
    const shift = typeof data.shift === "number" ? data.shift : 0;
    return shift >= PROB_SWING_THRESHOLD;
  }
  return Boolean(data.message);
}

export function relativeTime(at: Date, now = Date.now()): string {
  const sec = Math.max(0, Math.floor((now - at.getTime()) / 1000));
  if (sec < 10) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return at.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
