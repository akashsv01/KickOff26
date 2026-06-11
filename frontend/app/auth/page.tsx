"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SignupProfileFields } from "@/components/auth/SignupProfileFields";
import { FootballLoader } from "@/components/FootballLoader";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Team } from "@/lib/matchday";
import {
  COUNTRY_REGIONS,
  MAX_EXTRA_FOLLOWS,
  PREFERRED_LANGUAGES,
} from "@/lib/signupProfile";

function AuthForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, login, register, logout, loading } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [favoriteTeamId, setFavoriteTeamId] = useState<number | null>(null);
  const [countryRegion, setCountryRegion] = useState("");
  const [preferredLanguage, setPreferredLanguage] = useState("");
  const [followedTeamIds, setFollowedTeamIds] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const returnTo = searchParams.get("next") || "/matchday";

  useEffect(() => {
    if (mode !== "register") return;
    let cancelled = false;
    setTeamsLoading(true);
    api<Team[]>("/teams")
      .then((data) => {
        if (!cancelled) setTeams(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load teams - is the backend running?");
      })
      .finally(() => {
        if (!cancelled) setTeamsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [mode]);

  const handleFavoriteChange = useCallback((id: number) => {
    setFavoriteTeamId(id);
    setFollowedTeamIds((prev) => (prev.includes(id) ? prev : [id, ...prev]));
  }, []);

  const handleToggleFollow = useCallback(
    (id: number) => {
      if (id === favoriteTeamId) return;
      setFollowedTeamIds((prev) => {
        if (prev.includes(id)) return prev.filter((x) => x !== id);
        const extras = prev.filter((x) => x !== favoriteTeamId);
        if (extras.length >= MAX_EXTRA_FOLLOWS) return prev;
        return [...prev, id];
      });
    },
    [favoriteTeamId]
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        if (!favoriteTeamId) {
          setError("Pick your favorite national team to continue.");
          return;
        }
        const extraFollows = followedTeamIds.filter((id) => id !== favoriteTeamId);
        await register(email, username, password, {
          favorite_team_id: favoriteTeamId,
          country_region: countryRegion || undefined,
          preferred_language: preferredLanguage || undefined,
          followed_team_ids: extraFollows.length ? extraFollows : undefined,
        });
      }
      router.push(returnTo.startsWith("/") ? returnTo : "/matchday");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <FootballLoader layout="section" label="Loading…" />;
  }

  if (user) {
    return (
      <div className="auth-shell mx-auto max-w-md">
        <div className="auth-card">
          <h1 className="auth-title">Account</h1>
          <p className="mt-4 text-gray-300">
            Signed in as <span className="text-champagne">{user.username}</span> ({user.email})
          </p>
          {user.country_region && (
            <p className="mt-2 text-sm text-gray-400">Region: {user.country_region}</p>
          )}
          {user.followed_team_ids.length > 0 && (
            <p className="mt-1 text-sm text-gray-500">
              Following {user.followed_team_ids.length} team
              {user.followed_team_ids.length === 1 ? "" : "s"}
            </p>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              className="btn-primary"
              onClick={() => router.push(returnTo.startsWith("/") ? returnTo : "/matchday")}
            >
              Continue
            </button>
            <button
              className="btn-secondary"
              onClick={() => {
                logout();
                router.push("/auth");
              }}
            >
              Log out
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-shell mx-auto max-w-lg px-1">
      <h1 className="auth-title">Join KickOff26</h1>
      <p className="auth-subtitle">
        {mode === "login"
          ? "Sign in to save brackets, follow nations, and join fan rooms."
          : "Create your fan profile - pick your nation and teams to follow."}
      </p>

      <div className="auth-mode-toggle mt-5">
        <button
          type="button"
          className={mode === "login" ? "auth-mode-btn auth-mode-btn-active" : "auth-mode-btn"}
          onClick={() => setMode("login")}
        >
          Sign in
        </button>
        <button
          type="button"
          className={mode === "register" ? "auth-mode-btn auth-mode-btn-active" : "auth-mode-btn"}
          onClick={() => setMode("register")}
        >
          Create account
        </button>
      </div>

      <form onSubmit={submit} className="auth-card mt-6 space-y-4">
        <div>
          <label htmlFor="auth-email" className="auth-field-label">
            Email
          </label>
          <input
            id="auth-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="auth-field-input"
            required
          />
        </div>

        {mode === "register" && (
          <div>
            <label htmlFor="auth-username" className="auth-field-label">
              Display name
            </label>
            <input
              id="auth-username"
              type="text"
              autoComplete="username"
              placeholder="Min 3 characters"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="auth-field-input"
              minLength={3}
              required
            />
          </div>
        )}

        <div>
          <label htmlFor="auth-password" className="auth-field-label">
            Password
          </label>
          <input
            id="auth-password"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            placeholder="Min 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="auth-field-input"
            minLength={6}
            required
          />
        </div>

        {mode === "register" && (
          teamsLoading ? (
            <FootballLoader size="sm" label="Loading teams…" />
          ) : teams.length > 0 ? (
            <SignupProfileFields
              teams={teams}
              favoriteTeamId={favoriteTeamId}
              onFavoriteChange={handleFavoriteChange}
              countryRegion={countryRegion}
              onCountryChange={setCountryRegion}
              preferredLanguage={preferredLanguage}
              onLanguageChange={setPreferredLanguage}
              followedTeamIds={followedTeamIds}
              onToggleFollow={handleToggleFollow}
              countries={COUNTRY_REGIONS}
              languages={PREFERRED_LANGUAGES}
            />
          ) : null
        )}

        {error && <p className="auth-error">{error}</p>}

        <button
          type="submit"
          className="btn-primary flex w-full items-center justify-center gap-2"
          disabled={submitting || (mode === "register" && teamsLoading)}
        >
          {submitting ? (
            <FootballLoader size="sm" label="Please wait…" />
          ) : mode === "login" ? (
            "Sign In"
          ) : (
            "Create Account"
          )}
        </button>
      </form>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={<FootballLoader layout="section" label="Loading…" />}>
      <AuthForm />
    </Suspense>
  );
}
