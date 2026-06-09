"use client";

import { REACTION_EMOJIS } from "@/lib/watch";

type Props = {
  reactions: Record<string, number>;
  onReact: (emoji: string) => void;
};

export function WatchReactionBar({ reactions, onReact }: Props) {
  return (
    <div className="watch-reaction-bar" aria-label="Send a reaction">
      {REACTION_EMOJIS.map((emoji) => (
        <button
          key={emoji}
          type="button"
          className="watch-reaction-btn"
          onClick={() => onReact(emoji)}
          aria-label={`React ${emoji}`}
        >
          <span className="watch-reaction-emoji">{emoji}</span>
          <span className="watch-reaction-count">{reactions[emoji] ?? 0}</span>
        </button>
      ))}
    </div>
  );
}
