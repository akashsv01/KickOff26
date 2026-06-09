"use client";

import Link from "next/link";
import { FootballLoader } from "@/components/FootballLoader";
import { AppToast } from "@/components/AppToast";

export type BracketPersistScope = "groups" | "knockout";

const COPY: Record<
  BracketPersistScope,
  { save: string; clear: string; clearConfirm: string; loginSave: string; loginClear: string }
> = {
  groups: {
    save: "Save Group Results",
    clear: "Clear Saved Group Results",
    clearConfirm:
      "Clear saved group-stage results? Your knockout picks (if any) will be kept.",
    loginSave: "Please log in to save your group results.",
    loginClear: "Please log in to manage saved group results.",
  },
  knockout: {
    save: "Save Knockout Picks",
    clear: "Clear Knockout Picks",
    clearConfirm:
      "Clear saved knockout advancement picks? Your saved group results will be kept.",
    loginSave: "Please log in to save your knockout picks.",
    loginClear: "Please log in to manage saved knockout picks.",
  },
};

type Props = {
  scope: BracketPersistScope;
  saving: boolean;
  lastSaved: string | null;
  loggedIn: boolean;
  saveDisabled?: boolean;
  inline?: boolean;
  onSave: () => void;
  onClear: () => void;
  onLoginRequired: (action: "save" | "clear") => void;
};

export function BracketPersistActions({
  scope,
  saving,
  lastSaved,
  loggedIn,
  saveDisabled = false,
  inline = false,
  onSave,
  onClear,
  onLoginRequired,
}: Props) {
  const labels = COPY[scope];
  const guestHint = "Log in to save";

  function handleSave() {
    if (!loggedIn) {
      onLoginRequired("save");
      return;
    }
    if (!saveDisabled) onSave();
  }

  function handleClear() {
    if (!loggedIn) {
      onLoginRequired("clear");
      return;
    }
    if (!window.confirm(labels.clearConfirm)) return;
    onClear();
  }

  return (
    <div
      className={
        inline
          ? "flex flex-wrap items-center gap-2"
          : "ml-auto flex flex-wrap items-center gap-2 border-l border-app-faint/25 pl-3"
      }
    >
      {lastSaved ? (
        <span className="text-xs text-app-faint">
          Last saved {new Date(lastSaved).toLocaleString()}
        </span>
      ) : null}
      <button
        type="button"
        className={`bracket-persist-btn bracket-persist-btn-clear ${!loggedIn ? "bracket-persist-btn-guest" : ""}`}
        onClick={handleClear}
        title={!loggedIn ? guestHint : labels.clear}
        aria-label={!loggedIn ? `${labels.clear} (${guestHint})` : labels.clear}
      >
        {!loggedIn ? <span className="bracket-persist-lock" aria-hidden="true">🔒</span> : null}
        {labels.clear}
      </button>
      <button
        type="button"
        className={`bracket-persist-btn bracket-persist-btn-save ${!loggedIn ? "bracket-persist-btn-guest" : ""}`}
        onClick={handleSave}
        disabled={loggedIn && (saving || saveDisabled)}
        title={!loggedIn ? guestHint : labels.save}
        aria-label={!loggedIn ? `${labels.save} (${guestHint})` : labels.save}
      >
        {!loggedIn ? <span className="bracket-persist-lock" aria-hidden="true">🔒</span> : null}
        {saving ? <FootballLoader size="sm" label="Saving…" /> : labels.save}
      </button>
    </div>
  );
}

export function BracketLoginPrompt({
  scope,
  action,
  onDismiss,
}: {
  scope: BracketPersistScope;
  action: "save" | "clear";
  onDismiss: () => void;
}) {
  const message = action === "save" ? COPY[scope].loginSave : COPY[scope].loginClear;

  return (
    <AppToast
      message={message}
      onDismiss={onDismiss}
      actions={
        <>
          <Link href="/auth?next=/bracket" className="app-toast-link">
            Log in
          </Link>
          <button type="button" className="app-toast-dismiss" onClick={onDismiss}>
            Dismiss
          </button>
        </>
      }
    />
  );
}