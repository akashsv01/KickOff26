"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TrophyIcon } from "@/components/TrophyIcon";
import { useAuth } from "@/lib/auth";
import {
  STARTER_PROMPTS_GUEST,
  STARTER_PROMPTS_USER,
  fetchChatStatus,
  newMessageId,
  parseAssistantLines,
  streamChatReply,
  type ChatMessage,
} from "@/lib/assistant";

function ThinkingDots() {
  return (
    <span className="assistant-thinking" aria-label="Assistant is thinking">
      <span className="assistant-thinking-dot" />
      <span className="assistant-thinking-dot" />
      <span className="assistant-thinking-dot" />
    </span>
  );
}

function AssistantBubble({ content }: { content: string }) {
  const lines = parseAssistantLines(content);
  return (
    <div className="assistant-bubble assistant-bubble-ai">
      {lines.map((line, i) => {
        if (line.kind === "spacer") return <div key={i} className="assistant-msg-spacer" />;
        if (line.kind === "bullet") {
          return (
            <div key={i} className="assistant-msg-line assistant-msg-bullet">
              {line.text}
            </div>
          );
        }
        return (
          <p key={i} className="assistant-msg-line">
            {line.text}
          </p>
        );
      })}
    </div>
  );
}

export function AssistantChat() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [configured, setConfigured] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const starters = user ? STARTER_PROMPTS_USER : STARTER_PROMPTS_GUEST;

  useEffect(() => {
    fetchChatStatus()
      .then((s) => setConfigured(s.configured))
      .catch(() => setConfigured(false));
  }, []);

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking, open]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || thinking) return;

      setError(null);
      const userMsg: ChatMessage = { id: newMessageId(), role: "user", content: trimmed };
      const history = [...messages, userMsg];
      setMessages(history);
      setInput("");
      setThinking(true);

      const assistantId = newMessageId();
      let started = false;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChatReply(
          trimmed,
          messages,
          (delta) => {
            if (!started) {
              started = true;
              setMessages((prev) => [
                ...prev,
                { id: assistantId, role: "assistant", content: delta },
              ]);
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + delta } : m
                )
              );
            }
          },
          controller.signal
        );
        if (!started) {
          setMessages((prev) => [
            ...prev,
            {
              id: assistantId,
              role: "assistant",
              content:
                "Sorry — I couldn't reach the assistant. Please try again shortly.",
            },
          ]);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        const msg = err instanceof Error ? err.message : "Something went wrong";
        setError(msg);
        if (!started) {
          setMessages((prev) => [
            ...prev,
            {
              id: assistantId,
              role: "assistant",
              content:
                "Sorry — I couldn't reach the assistant. Please try again shortly.",
            },
          ]);
        }
      } finally {
        setThinking(false);
      }
    },
    [messages, thinking]
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void sendMessage(input);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage(input);
    }
  };

  return (
    <>
      {!open && (
        <button
          type="button"
          className="assistant-fab"
          onClick={() => setOpen(true)}
          aria-label="Open KickOff26 AI assistant"
        >
          <span className="assistant-fab-glow" aria-hidden />
          <TrophyIcon className="assistant-fab-icon" />
          <span className="assistant-fab-badge" aria-hidden>
            ✦
          </span>
        </button>
      )}

      {open && (
        <div className="assistant-root" role="dialog" aria-label="KickOff26 Assistant">
          <div className="assistant-backdrop" onClick={() => setOpen(false)} aria-hidden />
          <div className="assistant-panel md-glass">
            <div className="md-glass-content assistant-panel-inner">
              <header className="assistant-header">
                <div className="assistant-header-brand">
                  <span className="assistant-avatar-ring">
                    <TrophyIcon className="assistant-avatar-icon" />
                  </span>
                  <div>
                    <h2 className="assistant-title">KickOff26 Assistant</h2>
                    <p className="assistant-subtitle">
                      <span className="assistant-online-dot" aria-hidden />
                      Tournament guide
                      {!configured && " · setup pending"}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="assistant-close"
                  onClick={() => setOpen(false)}
                  aria-label="Close assistant"
                >
                  ×
                </button>
              </header>

              <div className="assistant-messages" ref={listRef}>
                {messages.length === 0 && (
                  <div className="assistant-welcome">
                    <p className="assistant-welcome-text">
                      Ask about fixtures, standings, teams, squads, or{" "}
                      {user ? "your followed teams and bracket picks" : "the tournament"}.
                    </p>
                    <div className="assistant-starters">
                      {starters.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          className="assistant-starter-chip"
                          onClick={() => void sendMessage(prompt)}
                          disabled={thinking}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`assistant-row assistant-row-${msg.role}`}
                  >
                    {msg.role === "assistant" && (
                      <span className="assistant-msg-avatar" aria-hidden>
                        <TrophyIcon className="h-5 w-4" />
                      </span>
                    )}
                    {msg.role === "user" ? (
                      <div className="assistant-bubble assistant-bubble-user">{msg.content}</div>
                    ) : msg.content ? (
                      <AssistantBubble content={msg.content} />
                    ) : null}
                  </div>
                ))}

                {thinking && messages[messages.length - 1]?.role === "user" && (
                  <div className="assistant-row assistant-row-assistant">
                    <span className="assistant-msg-avatar" aria-hidden>
                      <TrophyIcon className="h-5 w-4" />
                    </span>
                    <div className="assistant-bubble assistant-bubble-ai assistant-bubble-thinking">
                      <ThinkingDots />
                    </div>
                  </div>
                )}

                {error && <p className="assistant-error">{error}</p>}
              </div>

              <form className="assistant-input-row" onSubmit={onSubmit}>
                <textarea
                  ref={inputRef}
                  className="assistant-input"
                  rows={1}
                  placeholder="Ask about matches, teams, standings…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  disabled={thinking}
                  maxLength={2000}
                />
                <button
                  type="submit"
                  className="assistant-send"
                  disabled={thinking || !input.trim()}
                  aria-label="Send message"
                >
                  <svg viewBox="0 0 24 24" className="assistant-send-icon" aria-hidden>
                    <path d="M3.4 20.6 21 12 3.4 3.4l2.8 7.2L17 12l-10.8 1.4z" fill="currentColor" />
                  </svg>
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
