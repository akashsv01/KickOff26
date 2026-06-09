"use client";

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

type AppToastProps = {
  message: string;
  onDismiss: () => void;
  autoDismissMs?: number;
  actions?: ReactNode;
};

export function AppToast({
  message,
  onDismiss,
  autoDismissMs = 5000,
  actions,
}: AppToastProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (autoDismissMs <= 0) return;
    const timer = window.setTimeout(onDismiss, autoDismissMs);
    return () => window.clearTimeout(timer);
  }, [autoDismissMs, onDismiss, message]);

  if (!mounted) return null;

  return createPortal(
    <div className="app-toast-stack" role="status" aria-live="polite">
      <div className="app-toast">
        <p className="app-toast-message">{message}</p>
        {actions ? <div className="app-toast-actions">{actions}</div> : null}
      </div>
    </div>,
    document.body
  );
}
