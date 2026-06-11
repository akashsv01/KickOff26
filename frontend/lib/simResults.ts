import type { MostLikelyPathData } from "@/components/bracket/MostLikelyPath";

export type SimResultPayload = {
  iterations?: number;
  team_stats?: { champion?: Record<string, number> };
  most_likely_path?: MostLikelyPathData;
  most_likely_bracket?: Record<string, unknown>;
};

export type SimJobPoll = {
  job_id: string;
  status: string;
  iterations: number;
  progress?: { done: number; total: number };
  result?: SimResultPayload;
  error?: string | null;
  channel?: string | null;
};

/** Poll budget aligned with backend SIM_TIMEOUT_SEC (600s) and heavy runs (~4ms/iter). */
export function simPollDeadlineMs(iterations: number): number {
  const estimatedMs = iterations * 6 + 45_000;
  return Math.min(590_000, Math.max(90_000, estimatedMs));
}

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
      teams: finalTeams,
      champion: String(bracket.champion),
    },
  };
}
