"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FootballLoader } from "@/components/FootballLoader";
import { useAuth } from "@/lib/auth";

function AuthForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, login, register, logout, loading } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const returnTo = searchParams.get("next") || "/matchday";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, username, password);
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
      <div className="mx-auto max-w-md card">
        <h1 className="text-2xl font-bold text-champagne">Account</h1>
        <p className="mt-4 text-gray-300">
          Signed in as <span className="text-champagne">{user.username}</span> ({user.email})
        </p>
        <p className="mt-2 text-xs text-gray-500">
          Your account is saved in the database. Use the same email and password to sign in again.
        </p>
        <div className="mt-6 flex gap-3">
          <button className="btn-primary" onClick={() => router.push(returnTo.startsWith("/") ? returnTo : "/matchday")}>
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
    );
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-2xl font-bold text-champagne">Account</h1>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          className={mode === "login" ? "btn-primary" : "btn-secondary"}
          onClick={() => setMode("login")}
        >
          Login
        </button>
        <button
          type="button"
          className={mode === "register" ? "btn-primary" : "btn-secondary"}
          onClick={() => setMode("register")}
        >
          Register
        </button>
      </div>
      <form onSubmit={submit} className="card mt-6 space-y-4">
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-gray-600 bg-night px-3 py-2"
          required
        />
        {mode === "register" && (
          <input
            type="text"
            placeholder="Username (min 3 characters)"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-lg border border-gray-600 bg-night px-3 py-2"
            minLength={3}
            required
          />
        )}
        <input
          type="password"
          placeholder="Password (min 6 characters)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-lg border border-gray-600 bg-night px-3 py-2"
          minLength={6}
          required
        />
        {error && <p className="text-red-400">{error}</p>}
        <button type="submit" className="btn-primary flex w-full items-center justify-center gap-2" disabled={submitting}>
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
