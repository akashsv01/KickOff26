"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FootballLoader } from "@/components/FootballLoader";
import { api } from "@/lib/api";

function ResetForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await api("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      router.push("/auth?reset=success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset your password.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="auth-shell mx-auto max-w-md px-1">
        <h1 className="auth-title">Reset link invalid</h1>
        <div className="auth-card mt-6">
          <p className="text-gray-300">
            This reset link is missing or invalid. Please request a new one.
          </p>
          <Link href="/forgot-password" className="btn-primary mt-5 inline-block">
            Request a new link
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-shell mx-auto max-w-md px-1">
      <h1 className="auth-title">Choose a new password</h1>
      <p className="auth-subtitle">Enter and confirm your new password below.</p>
      <form onSubmit={submit} className="auth-card mt-6 space-y-4">
        <div>
          <label htmlFor="rp-password" className="auth-field-label">
            New password
          </label>
          <input
            id="rp-password"
            type="password"
            autoComplete="new-password"
            placeholder="Min 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="auth-field-input"
            minLength={6}
            required
          />
        </div>
        <div>
          <label htmlFor="rp-confirm" className="auth-field-label">
            Confirm new password
          </label>
          <input
            id="rp-confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="auth-field-input"
            minLength={6}
            required
          />
        </div>
        {error && <p className="auth-error">{error}</p>}
        <button
          type="submit"
          className="btn-primary flex w-full items-center justify-center gap-2"
          disabled={submitting}
        >
          {submitting ? <FootballLoader size="sm" label="Updating…" /> : "Update password"}
        </button>
        <p className="text-center text-sm">
          <Link href="/forgot-password" className="text-champagne hover:underline">
            Request a new link
          </Link>
        </p>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<FootballLoader layout="section" label="Loading…" />}>
      <ResetForm />
    </Suspense>
  );
}
