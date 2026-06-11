"use client";

import { useMemo, useState } from "react";
import { TeamFlag } from "@/components/TeamFlag";
import { MAX_EXTRA_FOLLOWS } from "@/lib/signupProfile";
import type { Team } from "@/lib/matchday";

type Props = {
  teams: Team[];
  favoriteTeamId: number | null;
  onFavoriteChange: (id: number) => void;
  countryRegion: string;
  onCountryChange: (value: string) => void;
  preferredLanguage: string;
  onLanguageChange: (value: string) => void;
  followedTeamIds: number[];
  onToggleFollow: (id: number) => void;
  countries: readonly string[];
  languages: readonly { value: string; label: string }[];
};

export function SignupProfileFields({
  teams,
  favoriteTeamId,
  onFavoriteChange,
  countryRegion,
  onCountryChange,
  preferredLanguage,
  onLanguageChange,
  followedTeamIds,
  onToggleFollow,
  countries,
  languages,
}: Props) {
  const [teamQuery, setTeamQuery] = useState("");

  const sortedTeams = useMemo(
    () => [...teams].sort((a, b) => a.name.localeCompare(b.name)),
    [teams]
  );

  const filteredTeams = useMemo(() => {
    if (!teamQuery.trim()) return sortedTeams;
    const q = teamQuery.toLowerCase();
    return sortedTeams.filter(
      (t) => t.code.toLowerCase().includes(q) || t.name.toLowerCase().includes(q)
    );
  }, [sortedTeams, teamQuery]);

  const extraFollowCount = followedTeamIds.filter((id) => id !== favoriteTeamId).length;

  return (
    <div className="auth-profile-fields space-y-5 border-t border-white/10 pt-5">
      <div>
        <label htmlFor="favorite-team" className="auth-field-label">
          Favorite national team <span className="text-copper">*</span>
        </label>
        <select
          id="favorite-team"
          value={favoriteTeamId ?? ""}
          onChange={(e) => onFavoriteChange(Number(e.target.value))}
          className="auth-field-input"
          required
        >
          <option value="" disabled>
            Select your nation…
          </option>
          {sortedTeams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.code})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="country-region" className="auth-field-label">
          Country / region
        </label>
        <select
          id="country-region"
          value={countryRegion}
          onChange={(e) => onCountryChange(e.target.value)}
          className="auth-field-input"
        >
          <option value="">Select (optional)</option>
          {countries.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <p className="auth-field-hint">Helps us surface local kickoff times and broadcast context.</p>
      </div>

      <div>
        <label htmlFor="preferred-language" className="auth-field-label">
          Preferred language
        </label>
        <select
          id="preferred-language"
          value={preferredLanguage}
          onChange={(e) => onLanguageChange(e.target.value)}
          className="auth-field-input"
        >
          {languages.map((lang) => (
            <option key={lang.value || "none"} value={lang.value}>
              {lang.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <label className="auth-field-label">Also follow (optional)</label>
          <span className="text-xs text-gray-500">
            Up to {MAX_EXTRA_FOLLOWS} besides your favorite
          </span>
        </div>
        <input
          type="search"
          placeholder="Search teams…"
          value={teamQuery}
          onChange={(e) => setTeamQuery(e.target.value)}
          className="auth-field-input mt-2"
        />
        <div className="mt-3 max-h-40 space-y-3 overflow-y-auto rounded-lg border border-white/10 bg-night/40 p-3">
          {filteredTeams.map((t) => {
            const isFavorite = t.id === favoriteTeamId;
            const selected = followedTeamIds.includes(t.id);
            const disabled =
              isFavorite || (!selected && extraFollowCount >= MAX_EXTRA_FOLLOWS);
            return (
              <button
                key={t.id}
                type="button"
                disabled={disabled}
                onClick={() => onToggleFollow(t.id)}
                className={[
                  "auth-team-chip",
                  selected ? "auth-team-chip-selected" : "",
                  isFavorite ? "auth-team-chip-favorite" : "",
                  disabled && !selected ? "opacity-40" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                title={isFavorite ? "Already your favorite team" : undefined}
              >
                <TeamFlag code={t.code} size="xs" />
                <span>{t.code}</span>
                {isFavorite && <span className="text-[10px] uppercase tracking-wide">★</span>}
              </button>
            );
          })}
        </div>
        <p className="auth-field-hint">
          Your favorite is followed automatically. Pick a few more for your MatchDay feed.
        </p>
      </div>
    </div>
  );
}
