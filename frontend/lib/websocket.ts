"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

type MessageHandler = (data: Record<string, unknown>) => void;

export function useWebSocket(token?: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Map<string, Set<MessageHandler>>>(new Map());
  const pendingRef = useRef<string[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const url = token ? `${WS_URL}?token=${token}` : WS_URL;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      pendingRef.current.forEach((channel) => {
        ws.send(JSON.stringify({ type: "subscribe", channel }));
      });
      pendingRef.current = [];
    };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        const channel = data.channel as string | undefined;
        if (channel) {
          handlersRef.current.get(channel)?.forEach((h) => h(data));
        }
        handlersRef.current.get("*")?.forEach((h) => h(data));
      } catch {
        /* ignore */
      }
    };

    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
    }, 30000);

    return () => {
      clearInterval(ping);
      ws.close();
      setConnected(false);
    };
  }, [token]);

  const subscribe = useCallback((channel: string, handler: MessageHandler) => {
    if (!handlersRef.current.has(channel)) handlersRef.current.set(channel, new Set());
    handlersRef.current.get(channel)!.add(handler);

    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "subscribe", channel }));
    } else {
      pendingRef.current.push(channel);
    }

    return () => {
      handlersRef.current.get(channel)?.delete(handler);
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "unsubscribe", channel }));
      }
    };
  }, []);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { connected, subscribe, send };
}
