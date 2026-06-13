"use client";

import { useState } from "react";
import Link from "next/link";
import { FootballLoader } from "@/components/FootballLoader";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
    } catch {
      // Intentionally ignore - the response is always neutral, never revealing
      // whether an account exists.
    }
    setDone(true);
    setSubmitting(false);
  }

  return (
    <div className="auth-shell mx-auto max-w-md px-1">
      <h1 className="auth-title">Reset your password</h1>
      <p className="auth-subtitle">
        Enter your account email and we will send you a reset link.
      </p>

      {done ? (
        <div className="auth-card mt-6">
          <p className="text-gray-300">
            If an account exists for that email, a reset link has been sent. Check your
            inbox (and your spam folder). The link expires in 45 minutes.
          </p>
          <Link href="/auth" className="btn-secondary mt-5 inline-block">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="auth-card mt-6 space-y-4">
          <div>
            <label htmlFor="fp-email" className="auth-field-label">
              Email
            </label>
            <input
              id="fp-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="auth-field-input"
              required
            />
          </div>
          <button
            type="submit"
            className="btn-primary flex w-full items-center justify-center gap-2"
            disabled={submitting}
          >
            {submitting ? <FootballLoader size="sm" label="Sending…" /> : "Send reset link"}
          </button>
          <p className="text-center text-sm">
            <Link href="/auth" className="text-champagne hover:underline">
              Back to sign in
            </Link>
          </p>
        </form>
      )}
    </div>
  );
}
