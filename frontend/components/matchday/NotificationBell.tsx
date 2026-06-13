"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  matchDetailHref,
  navigateToMatchDetail,
} from "@/lib/matchday";
import {
  MAX_VISIBLE_NOTIFICATIONS,
  notificationMeta,
  relativeTime,
  useMatchDayNotificationsOptional,
} from "@/lib/matchday-notifications";

export function NotificationBell() {
  const ctx = useMatchDayNotificationsOptional();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!ctx) return null;

  const { notifications, unreadCount, markAllRead } = ctx;
  const visible = notifications.slice(0, MAX_VISIBLE_NOTIFICATIONS);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        className="nav-icon-btn relative"
        aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
        onClick={() => {
          setOpen((v) => !v);
          if (!open) markAllRead();
        }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M12 2a5 5 0 0 0-5 5v2.1c0 .7-.3 1.4-.8 1.9L4.5 13.5A1 1 0 0 0 5.4 15H18.6a1 1 0 0 0 .9-1.5l-1.7-2.5c-.5-.5-.8-1.2-.8-1.9V7a5 5 0 0 0-5-5Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path d="M10 18a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-champagne px-1 text-[10px] font-bold tabular-nums text-[color:var(--app-gold-on)]">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="md-glass absolute right-0 top-full z-50 mt-2 w-80 max-w-[calc(100vw-2rem)] p-3 shadow-2xl">
          <div className="md-glass-content">
            <p className="md-label mb-2">Recent alerts</p>
            {visible.length === 0 ? (
              <p className="py-4 text-center text-sm text-app-faint">No alerts yet</p>
            ) : (
              <ul className="max-h-64 space-y-1 overflow-y-auto">
                {visible.map((n) => {
                  const meta = notificationMeta(n.type);
                  return (
                    <li key={n.id}>
                      <button
                        type="button"
                        className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm transition hover-surface"
                        onClick={() => {
                          setOpen(false);
                          if (n.matchId) navigateToMatchDetail(router.push, n.matchId);
                        }}
                      >
                        <span className="shrink-0 text-base leading-5" aria-hidden>
                          {meta.icon}
                        </span>
                        <span className="min-w-0">
                          <span className="block text-[10px] font-semibold uppercase tracking-wide text-app-faint">
                            {meta.label}
                          </span>
                          <span className="block text-app-secondary">{n.message}</span>
                          <span className="mt-0.5 block text-[10px] tabular-nums text-app-faint">
                            {relativeTime(n.at)}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function NotificationsPanel() {
  const ctx = useMatchDayNotificationsOptional();
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);

  if (!ctx) return null;

  const { notifications } = ctx;
  const visible = notifications.slice(0, MAX_VISIBLE_NOTIFICATIONS);

  return (
    <div className="md-glass p-4">
      <div className="md-glass-content">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 text-left"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          <span className="md-label">Notifications</span>
          <span className="flex items-center gap-2 text-xs tabular-nums text-app-faint">
            {notifications.length > 0 && <span>{notifications.length}</span>}
            <span className="text-champagne/80">{expanded ? "−" : "+"}</span>
          </span>
        </button>

        {expanded && (
          <ul className="mt-3 max-h-36 space-y-1 overflow-y-auto border-t border-[color:var(--app-border)] pt-3">
            {visible.length === 0 ? (
              <li className="text-xs text-app-faint">No meaningful alerts yet.</li>
            ) : (
              visible.map((n) => {
                const meta = notificationMeta(n.type);
                const body = (
                  <span className="flex items-start gap-2">
                    <span className="shrink-0 text-sm leading-4" aria-hidden>
                      {meta.icon}
                    </span>
                    <span className="min-w-0">
                      <span className="block">{n.message}</span>
                      <span className="mt-0.5 block tabular-nums text-app-faint">
                        {relativeTime(n.at)}
                      </span>
                    </span>
                  </span>
                );
                return (
                  <li key={n.id}>
                    {n.matchId ? (
                      <Link
                        href={matchDetailHref(n.matchId)}
                        className="block rounded-md px-1 py-1.5 text-xs text-app-secondary transition hover-surface hover:text-app"
                      >
                        {body}
                      </Link>
                    ) : (
                      <div className="px-1 py-1.5 text-xs text-app-secondary">{body}</div>
                    )}
                  </li>
                );
              })
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
