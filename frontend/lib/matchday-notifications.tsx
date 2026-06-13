"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  MAX_VISIBLE_NOTIFICATIONS,
  NOTIFICATION_STORE_CAP,
  relativeTime,
  shouldShowAlert,
  type MatchAlertPayload,
  type MatchNotification,
} from "@/lib/matchday";
import { useWebSocket } from "@/lib/websocket";

/** Per-type icon + label for the notification surfaces. */
export function notificationMeta(type: MatchNotification["type"]): { icon: string; label: string } {
  switch (type) {
    case "goal":
      return { icon: "⚽", label: "Goal" };
    case "penalty":
      return { icon: "⚽", label: "Penalty" };
    case "yellow_card":
      return { icon: "🟨", label: "Yellow card" };
    case "red_card":
      return { icon: "🟥", label: "Red card" };
    case "substitution":
      return { icon: "🔄", label: "Substitution" };
    case "var":
      return { icon: "📺", label: "VAR" };
    case "match_start":
      return { icon: "🟢", label: "Kickoff" };
    case "match_halftime":
      return { icon: "⏸", label: "Half time" };
    case "match_end":
      return { icon: "🏁", label: "Full time" };
    case "momentum":
      return { icon: "📈", label: "Momentum" };
    default:
      return { icon: "•", label: "Update" };
  }
}

type MatchDayNotificationsContextValue = {
  notifications: MatchNotification[];
  unreadCount: number;
  addFromAlert: (data: MatchAlertPayload) => void;
  addStatusNotification: (
    type: "match_start" | "match_halftime" | "match_end",
    matchId: number,
    message: string
  ) => void;
  markAllRead: () => void;
};

const MatchDayNotificationsContext = createContext<MatchDayNotificationsContextValue | null>(null);

function makeNotification(
  type: MatchNotification["type"],
  message: string,
  matchId?: number
): MatchNotification {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type,
    message,
    matchId,
    at: new Date(),
    read: false,
  };
}

export function MatchDayNotificationsProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<MatchNotification[]>([]);

  const push = useCallback((item: MatchNotification) => {
    setNotifications((prev) => {
      // De-duplicate by content (an alert can arrive on more than one channel
      // or be re-broadcast); keep only the most recent NOTIFICATION_STORE_CAP.
      const key = `${item.type}|${item.matchId ?? ""}|${item.message}`;
      if (prev.some((n) => `${n.type}|${n.matchId ?? ""}|${n.message}` === key)) return prev;
      return [item, ...prev].slice(0, NOTIFICATION_STORE_CAP);
    });
  }, []);

  const addFromAlert = useCallback(
    (data: MatchAlertPayload) => {
      if (!shouldShowAlert(data)) return;
      const type = String(data.type ?? "");
      const alertToNotif: Record<string, MatchNotification["type"]> = {
        goal_alert: "goal",
        yellow_card_alert: "yellow_card",
        red_card_alert: "red_card",
        substitution_alert: "substitution",
        penalty_alert: "penalty",
        var_alert: "var",
        match_start_alert: "match_start",
        match_halftime_alert: "match_halftime",
        match_end_alert: "match_end",
        momentum_alert: "momentum",
      };
      const notifType = alertToNotif[type] ?? "momentum";

      push(
        makeNotification(
          notifType,
          String(data.message ?? ""),
          typeof data.match_id === "number" ? data.match_id : undefined
        )
      );
    },
    [push]
  );

  const addStatusNotification = useCallback(
    (type: "match_start" | "match_halftime" | "match_end", matchId: number, message: string) => {
      push(makeNotification(type, message, matchId));
    },
    [push]
  );

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  // Single app-wide feed: collect alerts regardless of which page is open, so
  // the nav bell and the sidebar panel always reflect the live stream.
  const { subscribe } = useWebSocket();
  useEffect(() => {
    const unsub = subscribe("matches:alerts", (data) => addFromAlert(data as MatchAlertPayload));
    return unsub;
  }, [subscribe, addFromAlert]);

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications]
  );

  const value = useMemo(
    () => ({
      notifications,
      unreadCount,
      addFromAlert,
      addStatusNotification,
      markAllRead,
    }),
    [notifications, unreadCount, addFromAlert, addStatusNotification, markAllRead]
  );

  return (
    <MatchDayNotificationsContext.Provider value={value}>
      {children}
    </MatchDayNotificationsContext.Provider>
  );
}

export function useMatchDayNotifications() {
  const ctx = useContext(MatchDayNotificationsContext);
  if (!ctx) {
    throw new Error("useMatchDayNotifications must be used within MatchDayNotificationsProvider");
  }
  return ctx;
}

export function useMatchDayNotificationsOptional() {
  return useContext(MatchDayNotificationsContext);
}

export { relativeTime, MAX_VISIBLE_NOTIFICATIONS };
