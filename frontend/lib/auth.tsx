"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, clearToken, getToken, setToken } from "@/lib/api";
import { detectBrowserTimezone, type RegisterProfile } from "@/lib/signupProfile";

export type AuthUser = {
  id: number;
  email: string;
  username: string;
  followed_team_ids: number[];
  favorite_team_id: number | null;
  country_region: string | null;
  preferred_language: string | null;
  timezone: string | null;
  resolved_timezone?: string; // backend-resolved effective zone (timezone -> country -> UTC)
};

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    username: string,
    password: string,
    profile: RegisterProfile
  ) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const t = getToken();
    if (!t) {
      setUser(null);
      setTokenState(null);
      return;
    }
    try {
      const me = await api<AuthUser>("/auth/me");
      setUser(me);
      setTokenState(t);
    } catch {
      clearToken();
      setUser(null);
      setTokenState(null);
    }
  }, []);

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<{ access_token: string; user: AuthUser }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setToken(data.access_token);
    setTokenState(data.access_token);
    setUser(data.user);
  }, []);

  const register = useCallback(
    async (
      email: string,
      username: string,
      password: string,
      profile: RegisterProfile
    ) => {
      const body: Record<string, unknown> = {
        email,
        username,
        password,
        favorite_team_id: profile.favorite_team_id,
      };
      if (profile.country_region) body.country_region = profile.country_region;
      if (profile.preferred_language) body.preferred_language = profile.preferred_language;
      // Auto-detect the browser timezone at signup (no user input); the form
      // may also pass one explicitly via profile.timezone.
      const timezone = profile.timezone ?? detectBrowserTimezone();
      if (timezone) body.timezone = timezone;
      body.daily_digest_opt_in = !!profile.daily_digest_opt_in;
      if (profile.followed_team_ids?.length) {
        body.followed_team_ids = profile.followed_team_ids;
      }
      const data = await api<{ access_token: string; user: AuthUser }>("/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setToken(data.access_token);
      setTokenState(data.access_token);
      setUser(data.user);
    },
    []
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setTokenState(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, loading, login, register, logout, refreshUser }),
    [user, token, loading, login, register, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
