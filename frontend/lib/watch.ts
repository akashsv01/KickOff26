import type { Match } from "@/lib/matchday";
import { formatKickoff, matchDateKey } from "@/lib/matchday";

export type WatchPollOption = {
  index: number;
  label: string;
  votes: number;
  percentage: number;
};

export type WatchPoll = {
  id: number;
  room_id: number;
  question: string;
  options: WatchPollOption[];
  total_votes: number;
  /** This user's chosen option index, or null. Aggregate broadcasts carry null. */
  my_vote: number | null;
  created_by: string;
  created_at?: string | null;
  closes_at?: string | null;
  closed?: boolean;
};

export type WatchRoom = {
  id: number;
  match_id: number;
  name: string;
  active_poll: WatchPoll | null;
  polls: WatchPoll[];
  reactions: Record<string, number>;
  watcher_count: number;
  participants: WatchParticipant[];
};

export type WatchParticipant = {
  user_id: number | null;
  username: string;
};

export type WatchMessage = {
  id: number;
  room_id?: number;
  username: string;
  content: string;
  message_type: string;
  created_at: string;
};

export type RoomSummary = {
  match_id: number;
  room_id: number;
  watcher_count: number;
};

export type ReactionBurst = {
  id: string;
  emoji: string;
  x: number;
  drift: number;
};

export const REACTION_EMOJIS = ["⚽", "🔥", "😱", "👏", "😢"] as const;

/**
 * Max chat events kept in room state - chat messages AND join/leave notices
 * interleaved. Matches the API history limit (ROOM_HISTORY_LIMIT) so the in-memory
 * list and the fetched history agree on "last 20".
 */
export const WATCH_MESSAGE_CAP = 20;

export const OFFICIAL_TOURNAMENT_LINKS = {
  tournament: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",
  broadcasters:
    "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/fifa-world-cup-2026-broadcast-info",
} as const;

export function matchStatusLabel(status: string): "LIVE" | "UPCOMING" | "FINISHED" {
  if (status === "live") return "LIVE";
  if (status === "finished") return "FINISHED";
  return "UPCOMING";
}

export function summaryMap(summaries: RoomSummary[]): Map<number, RoomSummary> {
  return new Map(summaries.map((s) => [s.match_id, s]));
}

export function watcherCountForMatch(matchId: number, summaries: Map<number, RoomSummary>): number {
  return summaries.get(matchId)?.watcher_count ?? 0;
}

export function roomIdForMatch(matchId: number, summaries: Map<number, RoomSummary>): number | null {
  return summaries.get(matchId)?.room_id ?? null;
}

export function sortBrowseMatches(matches: Match[], summaries: Map<number, RoomSummary>): Match[] {
  return [...matches].sort((a, b) => {
    const liveA = a.status === "live" ? 1 : 0;
    const liveB = b.status === "live" ? 1 : 0;
    if (liveA !== liveB) return liveB - liveA;

    const watchA = watcherCountForMatch(a.id, summaries);
    const watchB = watcherCountForMatch(b.id, summaries);
    if (watchA !== watchB) return watchB - watchA;

    return (a.kickoff_at ?? "").localeCompare(b.kickoff_at ?? "");
  });
}

export function liveMatchesAll(matches: Match[]): Match[] {
  return matches.filter((m) => m.status === "live");
}

export function upNextTodayMatches(matches: Match[], today: string, zone?: string | null): Match[] {
  return matches.filter((m) => {
    if (m.status === "live") return false;
    const day = matchDateKey(m, zone);
    return day === today && m.status !== "finished";
  });
}

export function filterMatchesByDay(matches: Match[], day: string, zone?: string | null): Match[] {
  if (!day) return matches;
  return matches.filter((m) => matchDateKey(m, zone) === day);
}

export function filterMatchesBySearch(matches: Match[], query: string): Match[] {
  const q = query.trim().toLowerCase();
  if (!q) return matches;
  return matches.filter((m) => {
    const hay = [
      m.home_team?.code,
      m.home_team?.name,
      m.away_team?.code,
      m.away_team?.name,
      m.city,
      m.venue,
      m.group_letter,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });
}

export function formatMessageTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** Whole-number percentages for optimistic UI (server response is authoritative). */
function withPercentages(options: WatchPollOption[], total: number): WatchPollOption[] {
  return options.map((o) => ({
    ...o,
    percentage: total > 0 ? Math.round((o.votes / total) * 100) : 0,
  }));
}

/**
 * Optimistically reflect this user's vote before the server responds: move the
 * count off any previous pick, onto the new one, and re-derive totals so the
 * bars shift instantly. A no-op if the user already picked this option or the
 * poll is closed.
 */
export function optimisticVote(
  polls: WatchPoll[],
  pollId: number,
  optionIndex: number
): WatchPoll[] {
  return polls.map((poll) => {
    if (poll.id !== pollId || poll.closed || poll.my_vote === optionIndex) return poll;
    const options = poll.options.map((o) => ({ ...o }));
    if (poll.my_vote != null && options[poll.my_vote]) {
      options[poll.my_vote].votes = Math.max(0, options[poll.my_vote].votes - 1);
    }
    if (options[optionIndex]) options[optionIndex].votes += 1;
    const total = options.reduce((a, o) => a + o.votes, 0);
    return { ...poll, options: withPercentages(options, total), total_votes: total, my_vote: optionIndex };
  });
}

/** Replace a poll by id with an authoritative payload (e.g. a vote response). */
export function replacePoll(polls: WatchPoll[], updated: WatchPoll): WatchPoll[] {
  let found = false;
  const next = polls.map((p) => {
    if (p.id !== updated.id) return p;
    found = true;
    return updated;
  });
  return found ? next : [updated, ...next];
}

/**
 * Merge aggregate-only broadcasts (someone else voted) into local state. The
 * broadcast carries my_vote === null for everyone, so we keep each poll's
 * locally-known my_vote - the user's highlighted choice never flickers off.
 */
export function mergeAggregatePolls(prev: WatchPoll[], incoming: WatchPoll[]): WatchPoll[] {
  const prevById = new Map(prev.map((p) => [p.id, p]));
  return incoming.map((p) => ({ ...p, my_vote: p.my_vote ?? prevById.get(p.id)?.my_vote ?? null }));
}

export function matchResultPollPreset(homeCode: string, awayCode: string) {
  return {
    question: `Who wins - ${homeCode} vs ${awayCode}?`,
    options: [homeCode, "Draw", awayCode],
  };
}

export function avatarInitial(username: string): string {
  const ch = username.replace(/^guest$/i, "G").trim()[0];
  return (ch || "?").toUpperCase();
}

/** Stable hue for chat avatar rings from username. */
export function avatarHue(username: string): number {
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  return Math.abs(hash) % 360;
}

export type ChatGroup =
  | { kind: "system"; message: WatchMessage }
  | { kind: "group"; username: string; isOwn: boolean; messages: WatchMessage[] };

export function groupChatMessages(messages: WatchMessage[], currentUsername: string): ChatGroup[] {
  const groups: ChatGroup[] = [];
  for (const msg of messages) {
    if (msg.message_type === "system") {
      groups.push({ kind: "system", message: msg });
      continue;
    }
    const isOwn = msg.username === currentUsername;
    const last = groups[groups.length - 1];
    if (last?.kind === "group" && last.username === msg.username && last.isOwn === isOwn) {
      last.messages.push(msg);
    } else {
      groups.push({ kind: "group", username: msg.username, isOwn, messages: [msg] });
    }
  }
  return groups;
}

export function matchHeaderLine(match: Match, zone?: string | null): string {
  const parts = [formatKickoff(match.kickoff_at, zone)];
  if (match.venue) parts.push(match.venue);
  if (match.city) parts.push(match.city);
  if (match.group_letter) parts.push(`Group ${match.group_letter}`);
  return parts.filter(Boolean).join(" · ");
}
