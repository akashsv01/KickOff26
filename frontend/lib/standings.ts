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
  qualification: "auto" | "third" | null;
};

export type GroupStandings = {
  group: string;
  live: boolean;
  rows: StandingRow[];
};

export type StandingsResponse = {
  groups: GroupStandings[];
  best_thirds: string[];
  any_live: boolean;
};
