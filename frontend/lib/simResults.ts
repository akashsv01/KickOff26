import type { MostLikelyPathData } from "@/components/bracket/MostLikelyPath";

export type SimResultPayload = {
  iterations?: number;
  team_stats?: { champion?: Record<string, number> };
  most_likely_path?: MostLikelyPathData;
  most_likely_bracket?: Record<string, unknown>;
};

export function extractMostLikelyPath(
  result: SimResultPayload | Record<string, unknown> | null | undefined
): MostLikelyPathData | null {
  if (!result) return null;

  const payload = result as SimResultPayload;
  const path = payload.most_likely_path;
  if (path?.champion && Array.isArray(path.rounds) && path.rounds.length > 0) {
    return path;
  }

  const bracket = payload.most_likely_bracket;
  if (!bracket?.champion) return null;

  const finalRaw = bracket.final;
  const finalTeams = Array.isArray(finalRaw)
    ? (finalRaw as string[])
    : typeof finalRaw === "object" && finalRaw !== null
      ? Object.values(finalRaw as Record<string, string>)
      : [];

  return {
    champion: String(bracket.champion),
    rounds: [
      {
        id: "r32",
        label: "Round of 32",
        winners: (bracket.r32_winners as string[]) ?? [],
      },
      {
        id: "r16",
        label: "Round of 16",
        winners: (bracket.r16_winners as string[]) ?? [],
      },
      {
        id: "qf",
        label: "Quarter-finals",
        winners: (bracket.qf_winners as string[]) ?? [],
      },
      {
        id: "sf",
        label: "Semi-finals",
        winners: (bracket.sf_winners as string[]) ?? [],
      },
    ],
    final: {
      teams: finalTeams.length >= 2 ? finalTeams : [String(bracket.champion), String(bracket.champion)],
      champion: String(bracket.champion),
    },
  };
}

export function topChampionCode(result: SimResultPayload | null | undefined): string | null {
  const stats = result?.team_stats?.champion;
  if (!stats) return null;
  const sorted = Object.entries(stats).sort((a, b) => b[1] - a[1]);
  return sorted[0]?.[0] ?? null;
}

export type SimJobPoll = {
  status: string;
  progress?: { done: number; total: number };
  result?: SimResultPayload;
  error?: string;
};
