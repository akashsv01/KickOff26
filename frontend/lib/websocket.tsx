"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/lib/auth";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
const MAX_RECONNECT_MS = 30_000;

type MessageHandler = (data: Record<string, unknown>) => void;

type WebSocketContextValue = {
  connected: boolean;
  subscribe: (channel: string, handler: MessageHandler) => () => void;
  send: (data: Record<string, unknown>) => void;
  reconnectCount: number;
};

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

/** Single shared WebSocket for the app (avoids one connection per page). */
export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Map<string, Set<MessageHandler>>>(new Map());
  const pendingRef = useRef<Set<string>>(new Set());
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalClose = useRef(false);
  const [connected, setConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);

  useEffect(() => {
    intentionalClose.current = false;
    reconnectAttempt.current = 0;

    function replaySubscriptions() {
      pendingRef.current.forEach((channel) => {
        wsRef.current?.send(JSON.stringify({ type: "subscribe", channel }));
      });
    }

    function connect() {
      const url = token ? `${WS_URL}?token=${token}` : WS_URL;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttempt.current = 0;
        replaySubscriptions();
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (intentionalClose.current) return;
        const delay = Math.min(1000 * 2 ** reconnectAttempt.current, MAX_RECONNECT_MS);
        reconnectAttempt.current += 1;
        reconnectTimer.current = setTimeout(() => {
          setReconnectCount((n) => n + 1);
          connect();
        }, delay);
      };

      ws.onerror = () => setConnected(false);

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as Record<string, unknown>;
          const channel = data.channel as string | undefined;
          if (channel) {
            handlersRef.current.get(channel)?.forEach((h) => h(data));
          }
          handlersRef.current.get("*")?.forEach((h) => h(data));
        } catch {
          /* ignore malformed payloads */
        }
      };
    }

    connect();

    const ping = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 30_000);

    return () => {
      intentionalClose.current = true;
      clearInterval(ping);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [token]);

  const subscribe = useCallback((channel: string, handler: MessageHandler) => {
    if (!handlersRef.current.has(channel)) handlersRef.current.set(channel, new Set());
    handlersRef.current.get(channel)!.add(handler);
    pendingRef.current.add(channel);

    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "subscribe", channel }));
    }

    return () => {
      handlersRef.current.get(channel)?.delete(handler);
      if (handlersRef.current.get(channel)?.size === 0) {
        pendingRef.current.delete(channel);
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "unsubscribe", channel }));
        }
      }
    };
  }, []);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const value = useMemo(
    () => ({ connected, subscribe, send, reconnectCount }),
    [connected, subscribe, send, reconnectCount]
  );

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}

export function useWebSocket(_token?: string | null) {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error("useWebSocket must be used within WebSocketProvider");
  }
  return ctx;
}
