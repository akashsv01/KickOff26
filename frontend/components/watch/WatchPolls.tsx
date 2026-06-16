"use client";

import { useState } from "react";
import type { WatchPoll } from "@/lib/watch";

type Props = {
  polls: WatchPoll[];
  isLoggedIn: boolean;
  onVote: (pollId: number, optionIndex: number) => void;
};

export function WatchPolls({ polls, isLoggedIn, onVote }: Props) {
  const [votedFlash, setVotedFlash] = useState<string | null>(null);

  if (polls.length === 0) return null;

  function handleVote(pollId: number, optionIndex: number, disabled: boolean) {
    if (disabled) return;
    setVotedFlash(`${pollId}:${optionIndex}`);
    window.setTimeout(() => setVotedFlash(null), 450);
    onVote(pollId, optionIndex);
  }

  return (
    <div className="watch-polls">
      {polls.map((poll) => {
        const closed = !!poll.closed;
        return (
          <article key={poll.id} className="watch-poll-block">
            <p className="watch-poll-question">{poll.question}</p>
            <div className="watch-poll-meta">
              {poll.created_by && <span className="watch-poll-by">by {poll.created_by}</span>}
              {closed && <span className="watch-poll-closed">Closed</span>}
            </div>
            <ul className="watch-poll-options" role="list">
              {poll.options.map((opt) => {
                const selected = poll.my_vote === opt.index;
                const flash = votedFlash === `${poll.id}:${opt.index}`;
                const disabled = !isLoggedIn || closed;
                return (
                  <li key={opt.index}>
                    <button
                      type="button"
                      className={[
                        "watch-poll-option",
                        selected ? "watch-poll-option-selected" : "",
                        flash ? "watch-poll-option-flash" : "",
                        disabled ? "watch-poll-option-readonly" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      onClick={() => handleVote(poll.id, opt.index, disabled)}
                      aria-pressed={selected}
                      disabled={disabled}
                      title={
                        !isLoggedIn
                          ? "Log in to vote"
                          : closed
                            ? "This poll is closed"
                            : undefined
                      }
                    >
                      <span className="watch-poll-option-label">
                        {opt.label}
                        {selected ? <span className="watch-poll-your-vote">Your vote</span> : null}
                      </span>
                      <span
                        key={`${poll.id}-${opt.index}-${opt.votes}`}
                        className="watch-poll-option-count"
                      >
                        {opt.votes} · {opt.percentage}%
                      </span>
                      <span
                        className="watch-poll-bar"
                        style={{ width: `${opt.percentage}%` }}
                        aria-hidden
                      />
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className="watch-poll-total">
              {poll.total_votes} {poll.total_votes === 1 ? "vote" : "votes"}
              {!isLoggedIn ? " · log in to vote" : null}
            </p>
          </article>
        );
      })}
    </div>
  );
}
