"use client";

import Link from "next/link";
import { useState } from "react";
import type { Match } from "@/lib/matchday";
import { matchResultPollPreset, type ReactionBurst, type WatchMessage, type WatchRoom } from "@/lib/watch";
import { FloatingReactions } from "./FloatingReactions";
import { WatchChat } from "./WatchChat";
import { WatchPolls } from "./WatchPolls";
import { WatchReactionBar } from "./WatchReactionBar";
import { WatchRoomHeader } from "./WatchRoomHeader";

type Props = {
  room: WatchRoom;
  match: Match;
  messages: WatchMessage[];
  bursts: ReactionBurst[];
  connected: boolean;
  currentUsername: string;
  userId: number | null | undefined;
  isLoggedIn: boolean;
  onSendMessage: (text: string) => Promise<void>;
  onCreatePoll: (question: string, options: string[]) => Promise<void>;
  onVote: (pollId: number, optionIndex: number) => Promise<void>;
  onReact: (emoji: string) => Promise<void>;
};

export function WatchRoomPanel({
  room,
  match,
  messages,
  bursts,
  connected,
  currentUsername,
  userId,
  isLoggedIn,
  onSendMessage,
  onCreatePoll,
  onVote,
  onReact,
}: Props) {
  const [input, setInput] = useState("");
  const [pollQuestion, setPollQuestion] = useState("");
  const [pollOptions, setPollOptions] = useState(["", ""]);
  const [pollOpen, setPollOpen] = useState(false);
  const [tab, setTab] = useState<"chat" | "polls">("chat");
  const [sending, setSending] = useState(false);

  const polls = room.polls?.length ? room.polls : room.active_poll ? [room.active_poll] : [];

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setSending(true);
    try {
      await onSendMessage(text);
      setInput("");
    } finally {
      setSending(false);
    }
  }

  async function handleCreatePoll(e: React.FormEvent) {
    e.preventDefault();
    const opts = pollOptions.map((o) => o.trim()).filter(Boolean);
    if (!pollQuestion.trim() || opts.length < 2) return;
    await onCreatePoll(pollQuestion.trim(), opts);
    setPollQuestion("");
    setPollOptions(["", ""]);
    setPollOpen(false);
    setTab("polls");
  }

  function applyPreset() {
    const preset = matchResultPollPreset(
      match.home_team?.code ?? "Home",
      match.away_team?.code ?? "Away"
    );
    setPollQuestion(preset.question);
    setPollOptions(preset.options);
    setPollOpen(true);
    setTab("polls");
  }

  function updateOption(i: number, value: string) {
    setPollOptions((prev) => prev.map((o, idx) => (idx === i ? value : o)));
  }

  function addOption() {
    setPollOptions((prev) => (prev.length >= 6 ? prev : [...prev, ""]));
  }

  return (
    <section className="watch-room-panel" aria-label="Watch room">
      <WatchRoomHeader
        match={match}
        watcherCount={room.watcher_count}
        participants={room.participants}
        connected={connected}
      />

      <div className="watch-room-body md-glass">
        <FloatingReactions bursts={bursts} />

        <div className="watch-room-body-inner md-glass-content">
          {/* Priority 3 - Reactions (always visible, compact) */}
          <section className="watch-room-section watch-room-section-reactions" aria-label="Live reactions">
            <span className="watch-room-section-label">Live Reactions</span>
            <WatchReactionBar reactions={room.reactions ?? {}} onReact={onReact} />
          </section>

          {/* Chat / Polls tabs - chat is the default, dominant view */}
          <div className="watch-tabs" role="tablist" aria-label="Chat and polls">
            <button
              type="button"
              role="tab"
              id="watch-tab-chat"
              aria-selected={tab === "chat"}
              aria-controls="watch-panel-chat"
              className={`watch-tab${tab === "chat" ? " watch-tab-active" : ""}`}
              onClick={() => setTab("chat")}
            >
              Chat
            </button>
            <button
              type="button"
              role="tab"
              id="watch-tab-polls"
              aria-selected={tab === "polls"}
              aria-controls="watch-panel-polls"
              className={`watch-tab${tab === "polls" ? " watch-tab-active" : ""}`}
              onClick={() => setTab("polls")}
            >
              Polls
              {polls.length > 0 && <span className="watch-tab-badge">{polls.length}</span>}
            </button>
          </div>

          {tab === "chat" ? (
            <section
              id="watch-panel-chat"
              role="tabpanel"
              aria-labelledby="watch-tab-chat"
              className="watch-room-section watch-room-section-chat"
              aria-label="Chat"
            >
              <div className="watch-chat-shell">
                <WatchChat messages={messages} currentUsername={currentUsername} />
                {isLoggedIn ? (
                  <form onSubmit={handleSend} className="watch-chat-input-bar">
                    <label htmlFor="watch-chat-input" className="sr-only">
                      Message the room
                    </label>
                    <input
                      id="watch-chat-input"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      className="watch-input watch-input-chat"
                      placeholder="Message the room…"
                      maxLength={2000}
                      disabled={sending}
                      autoComplete="off"
                    />
                    <button
                      type="submit"
                      className="watch-pill-btn watch-pill-btn-primary watch-send-btn"
                      disabled={sending || !input.trim()}
                    >
                      Send
                    </button>
                  </form>
                ) : (
                  <div className="watch-login-gate" role="note">
                    <span className="watch-login-gate-text">Log in to chat with the room.</span>
                    <Link href="/auth" className="watch-pill-btn watch-pill-btn-primary watch-send-btn">
                      Log in
                    </Link>
                  </div>
                )}
              </div>
            </section>
          ) : (
            <section
              id="watch-panel-polls"
              role="tabpanel"
              aria-labelledby="watch-tab-polls"
              className="watch-room-section watch-room-section-pollstab"
              aria-label="Polls"
            >
              <div className="watch-polls-scrollarea">
                {polls.length > 0 ? (
                  <WatchPolls polls={polls} isLoggedIn={isLoggedIn} onVote={(id, opt) => onVote(id, opt)} />
                ) : (
                  <p className="watch-polls-empty">No active polls yet. Start one for the room.</p>
                )}
              </div>

              <div className="watch-poll-create-pinned">
                {!isLoggedIn ? (
                  <div className="watch-login-gate" role="note">
                    <span className="watch-login-gate-text">Log in to create polls.</span>
                    <Link href="/auth" className="watch-pill-btn watch-pill-btn-primary">
                      Log in
                    </Link>
                  </div>
                ) : !pollOpen ? (
                  <div className="watch-poll-create-actions">
                    <button type="button" className="watch-pill-btn watch-pill-btn-secondary" onClick={applyPreset}>
                      Match result preset
                    </button>
                    <button type="button" className="watch-pill-btn watch-pill-btn-primary" onClick={() => setPollOpen(true)}>
                      New custom poll
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handleCreatePoll} className="watch-poll-form">
                    <input
                      value={pollQuestion}
                      onChange={(e) => setPollQuestion(e.target.value)}
                      className="watch-input"
                      placeholder="Your question…"
                      maxLength={300}
                      aria-label="Poll question"
                    />
                    {pollOptions.map((opt, i) => (
                      <input
                        key={i}
                        value={opt}
                        onChange={(e) => updateOption(i, e.target.value)}
                        className="watch-input"
                        placeholder={`Option ${i + 1}`}
                        maxLength={80}
                        aria-label={`Poll option ${i + 1}`}
                      />
                    ))}
                    <div className="watch-poll-form-actions">
                      <button type="button" className="watch-pill-btn watch-pill-btn-ghost" onClick={() => setPollOpen(false)}>
                        Cancel
                      </button>
                      {pollOptions.length < 6 && (
                        <button type="button" className="watch-pill-btn watch-pill-btn-ghost" onClick={addOption}>
                          + Option
                        </button>
                      )}
                      <button
                        type="submit"
                        className="watch-pill-btn watch-pill-btn-primary"
                        disabled={!userId || !pollQuestion.trim() || pollOptions.filter((o) => o.trim()).length < 2}
                      >
                        Create poll
                      </button>
                    </div>
                    {!userId && <p className="watch-login-hint">Log in to create polls.</p>}
                  </form>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}
