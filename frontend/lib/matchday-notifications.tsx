"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import {
  MAX_VISIBLE_NOTIFICATIONS,
  NOTIFICATION_STORE_CAP,
  relativeTime,
  shouldShowAlert,
  type MatchAlertPayload,
  type MatchNotification,
} from "@/lib/matchday";

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
    setNotifications((prev) => [item, ...prev].slice(0, NOTIFICATION_STORE_CAP));
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
