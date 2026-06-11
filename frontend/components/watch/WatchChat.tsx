"use client";

import { useEffect, useMemo, useRef } from "react";
import { avatarHue, avatarInitial, formatMessageTime, groupChatMessages, type WatchMessage } from "@/lib/watch";

type Props = {
  messages: WatchMessage[];
  currentUsername: string;
};

const STICK_THRESHOLD_PX = 72;

export function WatchChat({ messages, currentUsername }: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const groups = useMemo(
    () => groupChatMessages(messages, currentUsername),
    [messages, currentUsername]
  );

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;

    function onScroll() {
      const node = scrollerRef.current;
      if (!node) return;
      const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
      stickToBottomRef.current = distanceFromBottom <= STICK_THRESHOLD_PX;
    }

    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || !stickToBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, messages[messages.length - 1]?.id]);

  return (
    <div ref={scrollerRef} className="watch-chat" aria-live="polite" role="log" aria-label="Room chat">
      {groups.length === 0 ? (
        <div className="watch-chat-empty">
          <p className="watch-chat-empty-title">The room is quiet</p>
          <p className="watch-chat-empty-sub">Break the ice - reactions and messages sync live for everyone here.</p>
        </div>
      ) : (
        <div className="watch-chat-messages">
          {groups.map((item) => {
            if (item.kind === "system") {
              return (
                <div key={item.message.id} className="watch-chat-system">
                  <span className="watch-chat-system-pill">{item.message.content}</span>
                </div>
              );
            }

            const { username, isOwn, messages: batch } = item;
            const hue = avatarHue(username);

            return (
              <div
                key={`${username}-${batch[0].id}`}
                className={["watch-chat-group", isOwn ? "watch-chat-group-own" : "watch-chat-group-other"].join(" ")}
              >
                {!isOwn && (
                  <span
                    className="watch-chat-avatar"
                    style={{ "--avatar-hue": String(hue) } as React.CSSProperties}
                    aria-hidden
                  >
                    {avatarInitial(username)}
                  </span>
                )}
                <div className="watch-chat-group-bubbles">
                  <div className="watch-chat-group-head">
                    {!isOwn && <span className="watch-chat-user">{username}</span>}
                    <time className="watch-chat-time" dateTime={batch[0].created_at}>
                      {formatMessageTime(batch[0].created_at)}
                    </time>
                  </div>
                  {batch.map((msg) => (
                    <div key={msg.id} className="watch-chat-bubble">
                      <p className="watch-chat-body">{msg.content}</p>
                    </div>
                  ))}
                </div>
                {isOwn && (
                  <span
                    className="watch-chat-avatar watch-chat-avatar-own"
                    style={{ "--avatar-hue": String(hue) } as React.CSSProperties}
                    aria-hidden
                  >
                    {avatarInitial(username)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
