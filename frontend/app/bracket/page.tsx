"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChampionCelebration } from "@/components/bracket/ChampionCelebration";
import { ChampionProbList } from "@/components/bracket/ChampionProbList";
import { GroupPanel } from "@/components/bracket/GroupPanel";
import { GroupStageToolbar } from "@/components/bracket/GroupStageToolbar";
import {
  BracketLoginPrompt,
  BracketPersistActions,
  type BracketPersistScope,
} from "@/components/bracket/BracketPersistActions";
import { BracketExportSheet } from "@/components/bracket/BracketExportSheet";
import { KnockoutBracket } from "@/components/bracket/KnockoutBracket";
import { MostLikelyPath } from "@/components/bracket/MostLikelyPath";
import { FootballLoader } from "@/components/FootballLoader";
import { AppToast } from "@/components/AppToast";
import {
  seedR32FromStandings,
  computeAllStandings,
  countDecidedResults,
  normalizeGroupResults,
  rankThirdPlaced,
  serializeGroupResults,
  simulateAllGroups,
  simulateGroupFixtures,
  type GroupResults,
  type MatchResult,
} from "@/lib/bracketGroups";
import { applyKnockoutPick } from "@/lib/knockoutBracket";
import { exportNodeToPdf, exportNodeToPng, formatExportError, logExportError } from "@/lib/exporters";
import { api, API_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  extractMostLikelyPath,
  type SimJobPoll,
  type SimResultPayload,
} from "@/lib/simResults";
import { useWebSocket } from "@/lib/websocket";

type Team = { id: number; name: string; code: string; elo: number };
type KnockoutRound = {
  id: string;
  label: string;
  slots: { slot: string; label: string }[];
};
type Structure = {
  groups: Record<string, Team[]>;
  fixtures: Record<
    string,
    {
      id: number;
      home: { code: string; name: string };
      away: { code: string; name: string };
      kickoff_at: string | null;
      city: string | null;
      venue: string | null;
      status: string;
      home_score: number | null;
      away_score: number | null;
    }[]
  >;
  standings: Record<string, unknown[]>;
  knockout: KnockoutRound[];
  teams_by_code: Record<string, Team>;
  match_odds: Record<string, { home: number; draw: number; away: number }>;
};

type SavedPicks = {
  picks: {
    group_results?: Record<string, MatchResult>;
    knockout?: Record<string, string>;
    slot_teams?: Record<string, string>;
  };
  updated_at: string | null;
};

export default function BracketPage() {
  const { user, token } = useAuth();
  const [tab, setTab] = useState<"groups" | "knockout" | "simulate">("groups");
  const [structure, setStructure] = useState<Structure | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [groupResults, setGroupResults] = useState<GroupResults>({});
  const [savedGroupResults, setSavedGroupResults] = useState<GroupResults>({});
  const [knockoutPicks, setKnockoutPicks] = useState<Record<string, string>>({});
  const [upsets, setUpsets] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const [savedSignature, setSavedSignature] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [loginPrompt, setLoginPrompt] = useState<{
    scope: BracketPersistScope;
    action: "save" | "clear";
  } | null>(null);
  const [simResult, setSimResult] = useState<Record<string, unknown> | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [iterations, setIterations] = useState(1000);
  const [championCode, setChampionCode] = useState("");
  const [simulating, setSimulating] = useState(false);
  const [simLiveMode, setSimLiveMode] = useState(false);
  const [liveChampionProbs, setLiveChampionProbs] = useState<Record<string, number> | null>(null);
  const { subscribe } = useWebSocket(token);
  const bracketExportSheetRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const simFinishRef = useRef(false);
  const simPathAppliedRef = useRef(false);
  const simUnsubRef = useRef<(() => void) | null>(null);

  const applySimResult = useCallback((result: SimResultPayload) => {
    const path = extractMostLikelyPath(result);
    const normalized = path ? { ...result, most_likely_path: path } : result;
    setSimResult(normalized as Record<string, unknown>);
    setLiveChampionProbs(null);
    if (path?.champion) setChampionCode(path.champion);
  }, []);

  const pollSimJob = useCallback(
    async (
      taskId: string,
      options?: {
        liveMode?: boolean;
        onProgress?: (progress: { done: number; total: number }) => void;
      }
    ): Promise<SimResultPayload> => {
      const deadline = Date.now() + 120_000;
      while (Date.now() < deadline) {
        const job = await api<SimJobPoll>(`/bracket/simulate/jobs/${taskId}`);
        if (options?.onProgress && job.progress) {
          options.onProgress(job.progress);
        }
        if (job.status === "complete" && job.result) {
          return job.result;
        }
        if (job.status === "failed") {
          throw new Error(job.error ?? "Simulation failed");
        }
        await new Promise((r) => setTimeout(r, options?.liveMode ? 350 : 400));
      }
      throw new Error("Simulation timed out - try fewer iterations or use Simulate (Live)");
    },
    []
  );

  const finishSimulation = useCallback(
    (result: SimResultPayload) => {
      const path = extractMostLikelyPath(result);
      const hasPath = Boolean(path);

      if (simFinishRef.current) {
        if (hasPath && !simPathAppliedRef.current) {
          applySimResult(result);
          simPathAppliedRef.current = true;
        }
        return;
      }

      applySimResult(result);
      if (hasPath) simPathAppliedRef.current = true;
      simFinishRef.current = true;
      setProgress(null);
      setSimLiveMode(false);
      setSimulating(false);
      simUnsubRef.current?.();
      simUnsubRef.current = null;
    },
    [applySimResult]
  );

  useEffect(() => {
    setLoading(true);
    api<Structure>("/bracket/structure")
      .then(setStructure)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load bracket"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!token) return;
    api<SavedPicks>("/bracket/picks")
      .then(({ picks, updated_at }) => {
        if (picks?.group_results) {
          const normalized = normalizeGroupResults(picks.group_results);
          setGroupResults(normalized);
          setSavedGroupResults(normalized);
          setSavedSignature(JSON.stringify(picks.group_results));
        }
        if (picks?.knockout) setKnockoutPicks(picks.knockout);
        if (updated_at) setLastSaved(updated_at);
      })
      .catch(() => {});
  }, [token]);

  const groupLetters = useMemo(
    () => (structure ? Object.keys(structure.groups).sort() : []),
    [structure]
  );

  const standingsByGroup = useMemo(() => {
    if (!structure) return {};
    return computeAllStandings(structure.groups, structure.fixtures, groupResults);
  }, [structure, groupResults]);

  const savedStandingsByGroup = useMemo(() => {
    if (!structure) return {};
    return computeAllStandings(structure.groups, structure.fixtures, savedGroupResults);
  }, [structure, savedGroupResults]);

  const thirdAdvancers = useMemo(() => rankThirdPlaced(standingsByGroup), [standingsByGroup]);

  const savedThirdAdvancers = useMemo(
    () => rankThirdPlaced(savedStandingsByGroup),
    [savedStandingsByGroup]
  );

  const savedR32SlotTeams = useMemo(() => {
    if (!structure || Object.keys(savedStandingsByGroup).length === 0) return {};
    return seedR32FromStandings(savedStandingsByGroup, savedThirdAdvancers);
  }, [structure, savedStandingsByGroup, savedThirdAdvancers]);

  const progressStats = useMemo(() => {
    if (!structure) return { decided: 0, total: 72 };
    return countDecidedResults(structure.fixtures, groupResults);
  }, [structure, groupResults]);

  const currentSignature = useMemo(
    () => JSON.stringify(serializeGroupResults(groupResults)),
    [groupResults]
  );

  const isComplete = progressStats.decided === progressStats.total;
  const isSavedCurrent = Boolean(lastSaved && savedSignature && savedSignature === currentSignature);
  const knockoutUnlocked = Boolean(user && isComplete && isSavedCurrent);

  const r32SlotTeams = useMemo(() => {
    if (!knockoutUnlocked) return {};
    return savedR32SlotTeams;
  }, [knockoutUnlocked, savedR32SlotTeams]);

  const showToast = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2800);
  }, []);

  const promptLogin = useCallback((scope: BracketPersistScope, action: "save" | "clear") => {
    setLoginPrompt({ scope, action });
  }, []);

  function toggleGroup(g: string) {
    setExpanded((prev) => ({ ...prev, [g]: !prev[g] }));
  }

  function setFixtureResult(fixtureId: number, result: MatchResult | null) {
    setGroupResults((prev) => {
      const next = { ...prev };
      if (result == null) delete next[fixtureId];
      else next[fixtureId] = result;
      return next;
    });
  }

  function pickKnockout(slotId: string, code: string) {
    setKnockoutPicks((prev) => {
      const next = applyKnockoutPick(prev, slotId, code);
      if (slotId === "final-1") {
        setChampionCode(code);
      } else if (!next["final-1"]) {
        setChampionCode("");
      }
      return next;
    });
  }

  async function saveGroupResults() {
    setSaving(true);
    try {
      const res = await api<{ updated_at?: string }>("/bracket/save/groups", {
        method: "POST",
        body: JSON.stringify({
          name: "My Bracket",
          picks: {
            version: 2,
            group_results: serializeGroupResults(groupResults),
            slot_teams: r32SlotTeams,
          },
        }),
      });
      const savedAt = res.updated_at ?? new Date().toISOString();
      setLastSaved(savedAt);
      setSavedGroupResults(groupResults);
      setSavedSignature(currentSignature);
      showToast("Group results saved");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to save group results");
    } finally {
      setSaving(false);
    }
  }

  async function saveKnockoutPicks() {
    setSaving(true);
    try {
      const res = await api<{ updated_at?: string }>("/bracket/save/knockout", {
        method: "POST",
        body: JSON.stringify({
          name: "My Bracket",
          picks: {
            version: 2,
            knockout: knockoutPicks,
          },
        }),
      });
      const savedAt = res.updated_at ?? new Date().toISOString();
      setLastSaved(savedAt);
      showToast("Knockout picks saved");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to save knockout picks");
    } finally {
      setSaving(false);
    }
  }

  async function clearGroupResults() {
    try {
      const res = await api<{ remaining?: boolean }>("/bracket/picks/groups", { method: "DELETE" });
      setGroupResults({});
      setSavedGroupResults({});
      setSavedSignature(null);
      if (!res.remaining) setLastSaved(null);
      showToast("Saved group results cleared");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to clear group results");
    }
  }

  async function clearKnockoutPicks() {
    try {
      const res = await api<{ remaining?: boolean }>("/bracket/picks/knockout", { method: "DELETE" });
      setKnockoutPicks({});
      setChampionCode("");
      if (!res.remaining) setLastSaved(null);
      showToast("Knockout picks cleared");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to clear knockout picks");
    }
  }

  async function handleExportBracket(kind: "png" | "pdf") {
    const node = bracketExportSheetRef.current;
    if (!node || !structure) return;
    setExporting(true);
    try {
      const champ = knockoutPicks["final-1"];
      const base = `kickoff26-bracket${champ ? `-${champ}` : ""}`;
      if (kind === "png") {
        await exportNodeToPng(node, `${base}.png`);
      } else {
        await exportNodeToPdf(node, `${base}.pdf`);
      }
      showToast(`Bracket exported as ${kind.toUpperCase()}`);
    } catch (err) {
      logExportError(`bracket ${kind}`, err);
      showToast(`Export failed: ${formatExportError(err)}`);
    } finally {
      setExporting(false);
    }
  }

  function resetWorkingState() {
    setGroupResults({});
  }

  function randomizeAll() {
    if (!structure) return;
    setGroupResults(
      simulateAllGroups(structure.fixtures, structure.match_odds, upsets, groupResults, false)
    );
  }

  function fillRemaining() {
    if (!structure) return;
    setGroupResults(
      simulateAllGroups(structure.fixtures, structure.match_odds, upsets, groupResults, true)
    );
  }

  function randomizeGroup(group: string) {
    if (!structure) return;
    setGroupResults((prev) =>
      simulateGroupFixtures(
        group,
        structure.fixtures[group] || [],
        structure.match_odds,
        upsets,
        prev,
        false
      )
    );
  }

  async function runSimulation() {
    simFinishRef.current = false;
    simPathAppliedRef.current = false;
    simUnsubRef.current?.();
    setSimResult(null);
    setProgress({ done: 0, total: iterations });
    setLiveChampionProbs(null);
    setSimLiveMode(true);
    setSimulating(true);
    try {
      const data = await api<{
        task_id: string;
        channel: string;
        status?: string;
      }>("/bracket/simulate", {
        method: "POST",
        body: JSON.stringify({ iterations }),
      });
      const taskId = data.task_id;

      simUnsubRef.current = subscribe(data.channel, (msg) => {
        if (msg.type === "sim_progress") {
          setProgress({ done: msg.done as number, total: msg.total as number });
          if (msg.partial_champion) {
            setLiveChampionProbs(msg.partial_champion as Record<string, number>);
          }
        }
        if (msg.type === "sim_error") {
          showToast(String(msg.error ?? "Simulation failed"));
          simFinishRef.current = true;
          setProgress(null);
          setSimLiveMode(false);
          setSimulating(false);
          simUnsubRef.current?.();
          simUnsubRef.current = null;
        }
        if (msg.type === "sim_complete" && msg.result) {
          finishSimulation(msg.result as SimResultPayload);
        }
      });

      pollSimJob(taskId, {
        liveMode: true,
        onProgress: (p) => {
          if (!simFinishRef.current) setProgress(p);
        },
      })
        .then((result) => finishSimulation(result))
        .catch((err) => {
          if (!simFinishRef.current) {
            showToast(err instanceof Error ? err.message : "Simulation failed");
            setProgress(null);
            setSimLiveMode(false);
            setSimulating(false);
            simUnsubRef.current?.();
            simUnsubRef.current = null;
          }
        });
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Simulation failed to start");
      setProgress(null);
      setSimLiveMode(false);
      setSimulating(false);
    }
  }

  async function runSyncSim() {
    simFinishRef.current = false;
    simPathAppliedRef.current = false;
    simUnsubRef.current?.();
    setSimResult(null);
    setProgress(null);
    setLiveChampionProbs(null);
    setSimLiveMode(false);
    setSimulating(true);
    try {
      const start = await api<{ task_id: string }>("/bracket/simulate/quick", {
        method: "POST",
        body: JSON.stringify({ iterations }),
      });
      const result = await pollSimJob(start.task_id);
      finishSimulation(result);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      if (!simFinishRef.current) {
        setSimulating(false);
      }
    }
  }

  const finalChampionCode = knockoutPicks["final-1"] ?? "";
  const simMostLikelyPath = extractMostLikelyPath(simResult as SimResultPayload | null);

  if (loading) {
    return <FootballLoader layout="section" label="Loading tournament bracket…" />;
  }

  if (error || !structure) {
    return (
      <div className="md-glass border-red-500/30 p-6 text-red-300">
        <h1 className="text-xl font-bold">Bracket unavailable</h1>
        <p className="mt-2 text-sm">{error || "No data returned"}</p>
      </div>
    );
  }

  const simChampionProbs =
    (simResult as { team_stats?: { champion?: Record<string, number> } } | null)?.team_stats
      ?.champion ??
    liveChampionProbs ??
    {};
  const showSimResults = Boolean(simResult) || Boolean(liveChampionProbs);
  const thirdAdvancerSet = new Set(thirdAdvancers);

  return (
    <div className="space-y-6">
      {toast ? <AppToast message={toast} onDismiss={() => setToast(null)} /> : null}
      {loginPrompt ? (
        <BracketLoginPrompt
          scope={loginPrompt.scope}
          action={loginPrompt.action}
          onDismiss={() => setLoginPrompt(null)}
        />
      ) : null}

      <header className="md-glass md-glass-hero overflow-hidden p-6">
        <div className="md-glass-content">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-champagne/80">
            2026 Tournament · 48 Teams · 12 Groups
          </p>
          <h1 className="mt-1 text-3xl font-bold text-champagne">Predictions</h1>
          <p className="mt-2 max-w-2xl text-sm text-app-muted">
            Enter group-stage results, auto-compute standings, seed the Round of 32, and export
            your knockout bracket to share.
          </p>
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        {(["groups", "knockout", "simulate"] as const).map((t) => (
          <button
            key={t}
            className={
              t === "knockout" && !knockoutUnlocked
                ? "md-btn-secondary opacity-60"
                : tab === t
                  ? "md-btn-primary"
                  : "md-btn-secondary"
            }
            onClick={() => {
              if (t === "knockout" && !knockoutUnlocked) {
                showToast(`Locked - ${progressStats.decided}/${progressStats.total} decided. Save to unlock.`);
                setTab("groups");
                return;
              }
              setTab(t);
            }}
            disabled={t === "knockout" && !knockoutUnlocked}
          >
            {t === "groups"
              ? "Group Stage"
              : t === "knockout"
                ? `Knockout${!knockoutUnlocked ? " 🔒" : ""}`
                : "Monte Carlo"}
          </button>
        ))}
      </div>

      {tab === "groups" && (
        <div className="space-y-4">
          <GroupStageToolbar
            decided={progressStats.decided}
            total={progressStats.total}
            upsets={upsets}
            onUpsetsChange={setUpsets}
            onRandomizeAll={randomizeAll}
            onFillRemaining={fillRemaining}
            onResetAll={resetWorkingState}
            onSave={saveGroupResults}
            onClear={clearGroupResults}
            onLoginRequired={(action) => promptLogin("groups", action)}
            saving={saving}
            lastSaved={lastSaved}
            loggedIn={Boolean(user)}
          />

          {thirdAdvancers.length > 0 ? (
            <div className="md-glass border border-app-faint/30 px-4 py-3 text-sm text-app-muted">
              <span className="font-semibold text-app">Best 8 third-placed: </span>
              {thirdAdvancers.join(", ")}
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {groupLetters.map((g) => (
              <GroupPanel
                key={g}
                group={g}
                teams={structure.groups[g]}
                standings={standingsByGroup[g] || []}
                fixtures={structure.fixtures[g] || []}
                expanded={expanded[g] ?? false}
                onToggle={() => toggleGroup(g)}
                groupResults={groupResults}
                onSetResult={setFixtureResult}
                onRandomizeGroup={() => randomizeGroup(g)}
                thirdAdvancers={thirdAdvancerSet}
              />
            ))}
          </div>
        </div>
      )}

      {tab === "knockout" && (
        <div className="space-y-4">
          {!knockoutUnlocked ? (
            <div className="md-glass border border-app-faint/35 p-5">
              <div className="md-glass-content space-y-2">
                <h3 className="text-lg font-black text-app">Knockout locked</h3>
                <p className="text-sm text-app-muted">
                  Complete and save all group-stage results to unlock the knockout bracket.
                </p>
                <p className="text-sm font-semibold text-app">
                  Progress: {progressStats.decided}/{progressStats.total} decided
                </p>
                <div className="flex flex-wrap gap-2 pt-2">
                  <button className="md-btn-primary" onClick={() => setTab("groups")}>
                    Go to Group Stage
                  </button>
                  {user ? (
                    <button
                      className="md-btn-secondary"
                      onClick={saveGroupResults}
                      disabled={saving || !isComplete}
                    >
                      {saving ? (
                        <FootballLoader size="sm" label="Saving…" />
                      ) : isComplete ? (
                        "Save Group Results to Unlock"
                      ) : (
                        "Finish Group Results"
                      )}
                    </button>
                  ) : (
                    <button
                      className="md-btn-secondary bracket-persist-btn-guest"
                      onClick={() => promptLogin("groups", "save")}
                      title="Log in to save"
                    >
                      <span className="bracket-persist-lock" aria-hidden="true">
                        🔒
                      </span>{" "}
                      Log in to Save & Unlock
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <>
              <p className="text-sm text-app-muted">
                Unlocked - seeded from your <span className="font-semibold">saved</span> group results.
                If you change results, you will need to re-save to unlock again.
              </p>
              <div className="space-y-4 rounded-2xl">
                <ChampionCelebration
                  championCode={finalChampionCode}
                  teamName={structure.teams_by_code[finalChampionCode]?.name}
                />
                <div className="md-glass overflow-hidden p-4">
                  <KnockoutBracket
                    rounds={structure.knockout}
                    picks={knockoutPicks}
                    slotTeams={r32SlotTeams}
                    onPick={pickKnockout}
                  />
                </div>
              </div>
              <div className="flex flex-wrap items-start gap-2">
                <button
                  type="button"
                  className="md-btn-secondary"
                  onClick={() => handleExportBracket("png")}
                  disabled={exporting}
                >
                  {exporting ? "Exporting…" : "Export bracket (PNG)"}
                </button>
                <button
                  type="button"
                  className="md-btn-secondary"
                  onClick={() => handleExportBracket("pdf")}
                  disabled={exporting}
                >
                  Export bracket (PDF)
                </button>
                <BracketPersistActions
                  scope={"knockout" satisfies BracketPersistScope}
                  inline
                  saving={saving}
                  lastSaved={lastSaved}
                  loggedIn={Boolean(user)}
                  onSave={saveKnockoutPicks}
                  onClear={clearKnockoutPicks}
                  onLoginRequired={(action) => promptLogin("knockout", action)}
                />
              </div>
            </>
          )}
        </div>
      )}

      {tab === "simulate" && (
        <div className="md-glass space-y-4 p-5">
          <div className="md-glass-content flex flex-wrap items-end gap-4">
            <label className="text-sm text-app">
              Iterations:{" "}
              <select
                value={iterations}
                onChange={(e) => setIterations(Number(e.target.value))}
                className="rounded border border-app-faint/20 bg-app/10 px-2 py-1 text-app"
              >
                <option value={1000}>1,000</option>
                <option value={10000}>10,000</option>
                <option value={50000}>50,000</option>
              </select>
            </label>
            <div className="sim-btn-wrap">
              <button
                className="md-btn-primary"
                onClick={runSimulation}
                disabled={simulating}
                title="Watch progress stream live over WebSocket"
              >
                Simulate (Live)
              </button>
              <span className="sim-btn-hint">Watch it run live</span>
            </div>
            <div className="sim-btn-wrap">
              <button
                className="md-btn-secondary"
                onClick={runSyncSim}
                disabled={simulating}
                title="Run on the server and return final results only"
              >
                Simulate (Quick)
              </button>
              <span className="sim-btn-hint">Skip to results</span>
            </div>
            {simulating && !simLiveMode ? (
              <FootballLoader size="sm" label="Running simulation…" />
            ) : null}
          </div>
          {simLiveMode && progress ? (
            <div>
              <div className="flex items-center gap-2 text-sm text-app-secondary">
                <FootballLoader size="sm" />
                <span>
                  Progress: {progress.done.toLocaleString()} / {progress.total.toLocaleString()}
                </span>
              </div>
              <div className="mt-1 h-2 rounded bg-app-faint/20">
                <div
                  className="h-2 rounded bg-champagne transition-all duration-300"
                  style={{ width: `${(progress.done / progress.total) * 100}%` }}
                />
              </div>
            </div>
          ) : null}
          {showSimResults ? (
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h3 className="sim-section-title">Champion Probabilities</h3>
                {simLiveMode && simulating && !simResult ? (
                  <p className="mt-1 text-xs text-app-muted">Converging as iterations complete…</p>
                ) : null}
                <ChampionProbList
                  probabilities={simChampionProbs}
                  animate={simLiveMode && simulating}
                />
              </div>
              <div>
                <h3 className="sim-section-title">Most Likely Knockout Path</h3>
                {simMostLikelyPath ? (
                  <MostLikelyPath path={simMostLikelyPath} />
                ) : simulating && simLiveMode ? (
                  <p className="mt-3 text-sm text-app-muted">
                    Full knockout path appears when the run finishes…
                  </p>
                ) : (
                  <MostLikelyPath path={null} />
                )}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {knockoutUnlocked && structure ? (
        <div
          className="bracket-export-mount"
          style={{
            position: "fixed",
            left: 0,
            top: 0,
            opacity: 0,
            pointerEvents: "none",
            zIndex: -1,
            overflow: "visible",
          }}
          aria-hidden
        >
          <BracketExportSheet
            ref={bracketExportSheetRef}
            username={user?.username ?? "Guest"}
            championCode={finalChampionCode}
            championName={structure.teams_by_code[finalChampionCode]?.name}
            rounds={structure.knockout}
            picks={knockoutPicks}
            slotTeams={r32SlotTeams}
          />
        </div>
      ) : null}

      {championCode && (
        <div className="md-glass p-5">
          <h3 className="font-semibold text-champagne">Champion Poster - {championCode}</h3>
          <img
            src={`${API_URL}/api/bracket/poster/${championCode}`}
            alt={`Predicted champion ${championCode}`}
            className="mt-4 max-w-md rounded border border-champagne/30"
          />
        </div>
      )}
    </div>
  );
}
