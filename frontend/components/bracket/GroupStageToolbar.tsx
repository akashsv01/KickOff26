"use client";

import {
  BracketPersistActions,
  type BracketPersistScope,
} from "@/components/bracket/BracketPersistActions";

type Props = {
  decided: number;
  total: number;
  upsets: boolean;
  onUpsetsChange: (value: boolean) => void;
  onRandomizeAll: () => void;
  onFillRemaining: () => void;
  onResetAll: () => void;
  onSave: () => void;
  onClear: () => void;
  onLoginRequired: (action: "save" | "clear") => void;
  saving: boolean;
  lastSaved: string | null;
  loggedIn: boolean;
  saveDisabled?: boolean;
};

export function GroupStageToolbar({
  decided,
  total,
  upsets,
  onUpsetsChange,
  onRandomizeAll,
  onFillRemaining,
  onResetAll,
  onSave,
  onClear,
  onLoginRequired,
  saving,
  lastSaved,
  loggedIn,
  saveDisabled,
}: Props) {
  const pct = total ? Math.round((decided / total) * 100) : 0;

  return (
    <div className="md-glass border border-app-faint/35 p-4 shadow-[0_12px_30px_rgba(0,0,0,0.14)]">
      <div className="md-glass-content space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-app">
              {decided} / {total} matches decided ({pct}%)
            </p>
            <div className="mt-2 h-1.5 w-full min-w-[200px] max-w-md overflow-hidden rounded-full bg-app-faint/20">
              <div
                className="h-full rounded-full bg-champagne transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-app-faint/30 bg-app/10 px-2 py-1 text-sm">
            <span
              className={`rounded-full px-2 py-0.5 transition ${
                !upsets
                  ? "bg-app/15 font-extrabold text-app ring-1 ring-app-faint/25"
                  : "font-medium text-app-faint"
              }`}
            >
              Realistic
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={upsets}
              className={`relative h-6 w-12 rounded-full border transition-all duration-200 ${
                upsets
                  ? "border-champagne/70 bg-champagne/35 shadow-[0_0_12px_rgba(212,175,55,0.22)]"
                  : "border-app-faint/40 bg-app-faint/20"
              }`}
              onClick={() => onUpsetsChange(!upsets)}
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full shadow transition-all duration-200 ${
                  upsets ? "left-[26px] bg-champagne" : "left-0.5 bg-app"
                }`}
              />
            </button>
            <span
              className={`rounded-full px-2 py-0.5 transition ${
                upsets
                  ? "bg-champagne/20 font-extrabold text-champagne ring-1 ring-champagne/35"
                  : "font-medium text-app-faint"
              }`}
            >
              Upsets
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-start gap-3">
          <div className="flex flex-wrap gap-2">
            <button type="button" className="md-btn-secondary text-sm" onClick={onRandomizeAll}>
              Randomize All
            </button>
            <button type="button" className="md-btn-secondary text-sm" onClick={onFillRemaining}>
              Fill Remaining
            </button>
            <button type="button" className="md-btn-secondary text-sm" onClick={onResetAll}>
              Reset All
            </button>
          </div>
          <BracketPersistActions
            scope={"groups" satisfies BracketPersistScope}
            saving={saving}
            lastSaved={lastSaved}
            loggedIn={loggedIn}
            saveDisabled={saveDisabled}
            onSave={onSave}
            onClear={onClear}
            onLoginRequired={onLoginRequired}
          />
        </div>
      </div>
    </div>
  );
}
