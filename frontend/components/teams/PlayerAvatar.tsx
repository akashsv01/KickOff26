"use client";

import { TeamFlag } from "@/components/TeamFlag";
import { playerInitials } from "@/lib/teams";

type Props = {
  name: string;
  teamCode: string;
  imageUrl?: string | null;
  size?: "md" | "lg";
};

export function PlayerAvatar({ name, teamCode, imageUrl, size = "md" }: Props) {
  const dim = size === "lg" ? "h-16 w-16" : "h-12 w-12";
  const initials = playerInitials(name);

  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt=""
        className={`${dim} shrink-0 rounded-full border-2 border-[color:var(--app-gold-border)] object-cover`}
      />
    );
  }

  return (
    <div
      className={`player-avatar-fallback ${dim} shrink-0`}
      aria-hidden
      title={name}
    >
      <TeamFlag code={teamCode} size={size === "lg" ? "md" : "sm"} className="player-avatar-flag" />
      <span className="player-avatar-initials">{initials}</span>
    </div>
  );
}
