"use client";

export type Toast = { id: string; message: string; type: "goal" | "card" | "momentum" };

const STYLES: Record<Toast["type"], string> = {
  goal: "border-green-500/40 bg-green-950/75 text-green-100",
  card: "border-red-500/40 bg-red-950/75 text-red-100",
  momentum: "border-yellow-500/40 bg-yellow-950/75 text-yellow-100",
};

export function ToastStack({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`md-toast px-4 py-3 text-sm ${STYLES[t.type]}`}
        >
          <div className="flex items-start justify-between gap-2">
            <span>{t.message}</span>
            <button
              type="button"
              className="text-xs opacity-60 transition hover:opacity-100"
              onClick={() => onDismiss(t.id)}
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
