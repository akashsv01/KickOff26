"use client";

import { avatarInitial } from "@/lib/watch";
import type { WatchParticipant } from "@/lib/watch";

export function WatchPresenceStrip({
  count,
  participants,
}: {
  count: number;
  participants: WatchParticipant[];
}) {
  const visible = participants.slice(0, 8);
  const overflow = Math.max(0, participants.length - visible.length);

  return (
    <div className="watch-presence-strip" aria-label={`${count} fans watching`}>
      {visible.length > 0 && (
        <ul className="watch-presence-avatars" aria-hidden>
          {visible.map((p, i) => (
            <li key={`${p.username}-${p.user_id ?? i}`} className="watch-presence-avatar" title={p.username}>
              {avatarInitial(p.username)}
            </li>
          ))}
          {overflow > 0 && <li className="watch-presence-overflow">+{overflow}</li>}
        </ul>
      )}
      <span className="watch-presence-strip-count">
        <span className="watch-watching-dot" aria-hidden />
        <strong>{count}</strong>
        <span className="watch-presence-label">watching</span>
      </span>
    </div>
  );
}

export function WatchPresence({
  count,
  participants,
}: {
  count: number;
  participants: WatchParticipant[];
}) {
  return <WatchPresenceStrip count={count} participants={participants} />;
}
