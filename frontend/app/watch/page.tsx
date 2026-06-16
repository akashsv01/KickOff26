"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { FootballLoader } from "@/components/FootballLoader";
import { WatchRoomBrowser } from "@/components/watch/WatchRoomBrowser";
import { WatchRoomPanel } from "@/components/watch/WatchRoomPanel";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type Match } from "@/lib/matchday";
import {
  mergeAggregatePolls,
  optimisticVote,
  replacePoll,
  summaryMap,
  type ReactionBurst,
  type RoomSummary,
  type WatchMessage,
  type WatchPoll,
  type WatchRoom,
  WATCH_MESSAGE_CAP,
} from "@/lib/watch";
import { useWebSocket } from "@/lib/websocket";

export default function WatchPage() {
  return (
    <Suspense fallback={<FootballLoader layout="section" label="Loading Fan Rooms…" />}>
      <WatchPageContent />
    </Suspense>
  );
}

function WatchPageContent() {
  const searchParams = useSearchParams();
  const { user, token } = useAuth();
  const { connected, subscribe } = useWebSocket(token);

  const [matches, setMatches] = useState<Match[]>([]);
  const [summaries, setSummaries] = useState<RoomSummary[]>([]);
  const [room, setRoom] = useState<WatchRoom | null>(null);
  const [match, setMatch] = useState<Match | null>(null);
  const [messages, setMessages] = useState<WatchMessage[]>([]);
  const [bursts, setBursts] = useState<ReactionBurst[]>([]);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const summaryByMatch = useMemo(() => summaryMap(summaries), [summaries]);
  const currentUsername = user?.username ?? "guest";

  const applyMatchUpdate = useCallback((updated: Match) => {
    setMatches((prev) => prev.map((m) => (m.id === updated.id ? { ...m, ...updated } : m)));
    setMatch((prev) => (prev?.id === updated.id ? { ...prev, ...updated } : prev));
  }, []);

  useEffect(() => {
    Promise.all([
      api<Match[]>("/matchday/matches"),
      api<RoomSummary[]>("/rooms/summary"),
    ])
      .then(([m, s]) => {
        setMatches(m);
        setSummaries(s);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!connected) return;
    return subscribe("matches:live", (data) => {
      if (data.type === "match_update" && data.match) {
        applyMatchUpdate(data.match as Match);
      }
    });
  }, [connected, subscribe, applyMatchUpdate]);

  useEffect(() => {
    if (!connected) return;
    return subscribe("watch:lobby", (data) => {
      if (data.type !== "presence_updated" || !data.match_id) return;
      setSummaries((prev) =>
        prev.map((s) =>
          s.match_id === data.match_id
            ? { ...s, watcher_count: Number(data.count) || 0 }
            : s
        )
      );
    });
  }, [connected, subscribe]);

  const joinRoom = useCallback(
    async (matchId: number) => {
      setJoining(true);
      setSidebarOpen(false);
      try {
        let targetRoom: WatchRoom | null = null;
        const rooms = await api<WatchRoom[]>(`/rooms/match/${matchId}`);
        if (rooms.length > 0) {
          targetRoom = rooms[0];
        } else {
          targetRoom = await api<WatchRoom>("/rooms", {
            method: "POST",
            body: JSON.stringify({ match_id: matchId }),
          });
          setSummaries((prev) => [
            ...prev.filter((s) => s.match_id !== matchId),
            { match_id: matchId, room_id: targetRoom!.id, watcher_count: 0 },
          ]);
        }
        const m = matches.find((x) => x.id === matchId) ?? (await api<Match[]>(`/matchday/matches`)).find((x) => x.id === matchId);
        if (m) setMatch(m);
        const fresh = await api<WatchRoom>(`/rooms/${targetRoom.id}`);
        setRoom(fresh);
        const msgs = await api<WatchMessage[]>(`/rooms/${targetRoom.id}/messages`);
        setMessages(msgs.slice(-WATCH_MESSAGE_CAP));
      } catch (err) {
        console.error(err);
      } finally {
        setJoining(false);
      }
    },
    [matches]
  );

  useEffect(() => {
    const mid = searchParams.get("match");
    if (mid && matches.length) {
      const id = Number(mid);
      if (Number.isFinite(id)) joinRoom(id);
    }
  }, [searchParams, matches.length, joinRoom]);

  useEffect(() => {
    if (!room || !connected) return;

    const roomChannel = `room:${room.id}`;
    const matchChannel = `match:${room.match_id}`;

    const unsubRoom = subscribe(roomChannel, (data) => {
        if (data.type === "new_message" && data.message) {
        const msg = data.message as WatchMessage;
        setMessages((prev) => {
          if (prev.some((m) => m.id === msg.id)) return prev;
          return [...prev.slice(-(WATCH_MESSAGE_CAP - 1)), msg];
        });
      }
      if (data.type === "poll_created" || data.type === "poll_updated") {
        // Broadcasts carry aggregate counts only (my_vote === null for everyone);
        // merge them in while preserving this client's own highlighted choice.
        if (data.polls) {
          setRoom((prev) =>
            prev
              ? { ...prev, polls: mergeAggregatePolls(prev.polls ?? [], data.polls as WatchPoll[]) }
              : prev
          );
        } else if (data.poll) {
          setRoom((prev) => {
            if (!prev) return prev;
            const merged = mergeAggregatePolls(prev.polls ?? [], [data.poll as WatchPoll]);
            return { ...prev, polls: replacePoll(prev.polls ?? [], merged[0]) };
          });
        }
      }
      if (data.type === "reaction_updated") {
        setRoom((prev) =>
          prev ? { ...prev, reactions: data.reactions as Record<string, number> } : prev
        );
      }
      if (data.type === "reaction_burst" && data.emoji) {
        const id = `${Date.now()}-${Math.random()}`;
        const x = 10 + Math.random() * 80;
        const drift = (Math.random() - 0.5) * 80;
        setBursts((prev) => [...prev.slice(-30), { id, emoji: String(data.emoji), x, drift }]);
        setTimeout(() => setBursts((prev) => prev.filter((b) => b.id !== id)), 2800);
      }
      if (data.type === "presence_updated") {
        setRoom((prev) =>
          prev
            ? {
                ...prev,
                watcher_count: Number(data.count) || 0,
                participants: (data.participants as WatchRoom["participants"]) ?? [],
              }
            : prev
        );
        setSummaries((prev) =>
          prev.map((s) =>
            s.room_id === room.id ? { ...s, watcher_count: Number(data.count) || 0 } : s
          )
        );
      }
    });

    const unsubMatch = subscribe(matchChannel, (data) => {
      if (data.type === "match_update" && data.match) {
        applyMatchUpdate(data.match as Match);
      }
    });

    return () => {
      unsubRoom();
      unsubMatch();
    };
  }, [room?.id, room?.match_id, connected, subscribe, applyMatchUpdate]);

  async function sendMessage(text: string) {
    if (!room) return;
    await api(`/rooms/${room.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ content: text }),
    });
  }

  async function createPoll(question: string, options: string[]) {
    if (!room || !user) return;
    await api(`/rooms/${room.id}/poll`, {
      method: "POST",
      body: JSON.stringify({ question, options }),
    });
  }

  async function votePoll(pollId: number, optionIndex: number) {
    if (!room || !user) return;
    // Reflect the choice instantly, then reconcile with the authoritative response.
    setRoom((prev) =>
      prev ? { ...prev, polls: optimisticVote(prev.polls ?? [], pollId, optionIndex) } : prev
    );
    try {
      const updated = await api<WatchPoll>(`/rooms/${room.id}/polls/${pollId}/vote`, {
        method: "POST",
        body: JSON.stringify({ option: optionIndex }),
      });
      setRoom((prev) => (prev ? { ...prev, polls: replacePoll(prev.polls ?? [], updated) } : prev));
    } catch (err) {
      console.error(err);
      // On failure, reload the persisted state so the UI matches the server.
      const fresh = await api<WatchPoll[]>(`/rooms/${room.id}/polls`).catch(() => null);
      if (fresh) setRoom((prev) => (prev ? { ...prev, polls: fresh } : prev));
    }
  }

  async function react(emoji: string) {
    if (!room) return;
    await api(`/rooms/${room.id}/reactions?emoji=${encodeURIComponent(emoji)}`, { method: "POST" });
  }

  if (loading) {
    return <FootballLoader layout="section" label="Loading Fan Rooms…" />;
  }

  return (
    <div className="matchday-shell watch-shell">
      <header className="watch-page-header">
        <div>
          <h1 className="watch-page-title">Watch Parties</h1>
          <p className="watch-page-sub">Real-time fan rooms for every match - chat, polls, and live reactions.</p>
        </div>
        <span className={connected ? "watch-live-indicator" : "watch-offline-indicator"}>
          <span className="watch-live-dot" aria-hidden />
          {connected ? "Live" : "Offline"}
        </span>
      </header>

      <div className={`watch-layout${sidebarOpen ? " watch-layout-sidebar-open" : ""}`}>
        <div className={`watch-layout-sidebar${sidebarOpen ? " watch-sidebar-expanded" : ""}`}>
          <button
            type="button"
            className="watch-sidebar-toggle watch-pill-btn watch-pill-btn-secondary"
            aria-expanded={sidebarOpen}
            aria-controls="watch-room-browser"
            onClick={() => setSidebarOpen((v) => !v)}
          >
            {sidebarOpen ? "Hide rooms" : "Browse rooms"}
          </button>

          <WatchRoomBrowser
            matches={matches}
            summaries={summaryByMatch}
            activeRoomId={room?.id ?? null}
            onJoin={joinRoom}
          />
        </div>

        <div className="watch-main">
          {joining && !room ? (
            <FootballLoader layout="inline" label="Joining room…" />
          ) : room && match ? (
            <WatchRoomPanel
              room={room}
              match={match}
              messages={messages}
              bursts={bursts}
              connected={connected}
              currentUsername={currentUsername}
              userId={user?.id}
              isLoggedIn={!!user}
              onSendMessage={sendMessage}
              onCreatePoll={createPoll}
              onVote={votePoll}
              onReact={react}
            />
          ) : (
            <div className="watch-join-placeholder md-glass">
              <div className="md-glass-content">
                <h2 className="md-section-title">Pick a match</h2>
                <p className="watch-join-placeholder-text">
                  Choose a live match or upcoming fixture from the left to join the fan room.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
