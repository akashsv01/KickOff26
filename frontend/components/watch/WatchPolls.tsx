"use client";

import { useMemo, useState } from "react";
import { getGuestId, pollTotals, voterKey, type WatchPoll } from "@/lib/watch";

type Props = {
  polls: WatchPoll[];
  userId: number | null | undefined;
  onVote: (pollId: string, option: string) => void;
};

export function WatchPolls({ polls, userId, onVote }: Props) {
  const guestId = useMemo(() => getGuestId(), []);
  const key = voterKey(userId, guestId);
  const [votedFlash, setVotedFlash] = useState<string | null>(null);

  if (polls.length === 0) return null;

  function handleVote(pollId: string, option: string) {
    setVotedFlash(`${pollId}:${option}`);
    window.setTimeout(() => setVotedFlash(null), 450);
    onVote(pollId, option);
  }

  return (
    <div className="watch-polls">
      {polls.map((poll) => {
        const total = pollTotals(poll.options);
        const myVote = poll.votes?.[key];
        return (
          <article key={poll.id} className="watch-poll-block">
            <p className="watch-poll-question">{poll.question}</p>
            {poll.created_by && <p className="watch-poll-by">by {poll.created_by}</p>}
            <ul className="watch-poll-options" role="list">
              {Object.entries(poll.options).map(([opt, count]) => {
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                const selected = myVote === opt;
                const flash = votedFlash === `${poll.id}:${opt}`;
                return (
                  <li key={opt}>
                    <button
                      type="button"
                      className={[
                        "watch-poll-option",
                        selected ? "watch-poll-option-selected" : "",
                        flash ? "watch-poll-option-flash" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      onClick={() => handleVote(poll.id, opt)}
                      aria-pressed={selected}
                    >
                      <span className="watch-poll-option-label">
                        {opt}
                        {selected ? <span className="watch-poll-your-vote">Your pick</span> : null}
                      </span>
                      <span key={`${poll.id}-${opt}-${count}`} className="watch-poll-option-count">
                        {count} · {pct}%
                      </span>
                      <span className="watch-poll-bar" style={{ width: `${pct}%` }} aria-hidden />
                    </button>
                  </li>
                );
              })}
            </ul>
          </article>
        );
      })}
    </div>
  );
}
