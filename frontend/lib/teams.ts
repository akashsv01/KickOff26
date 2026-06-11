export type SquadPlayer = {
  jersey: number | null;
  name: string;
  position: string;
  club: string | null;
  is_captain?: boolean;
};

export type PlayerToWatch = {
  player: string;
  reason: string;
  image_url: string | null;
};

export type TeamProfile = {
  team: {
    id: number;
    name: string;
    code: string;
    group_letter: string | null;
    elo_rating: number;
    flag_url: string | null;
  };
  coach: string | null;
  coach_source: string | null;
  coach_display: string;
  squad: {
    status: "loading" | "ready" | "unavailable";
    players_by_position: Record<string, SquadPlayer[]>;
    fetched_at: string | null;
  };
  player_to_watch: PlayerToWatch | null;
};

export const SQUAD_POSITION_LABELS: Record<string, string> = {
  GK: "Goalkeepers",
  DEF: "Defenders",
  MID: "Midfielders",
  FWD: "Forwards",
  OTHER: "Other",
};

export const SQUAD_POSITION_ORDER = ["GK", "DEF", "MID", "FWD", "OTHER"] as const;

export function playerInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[parts.length - 1][0] ?? ""}`.toUpperCase();
}
