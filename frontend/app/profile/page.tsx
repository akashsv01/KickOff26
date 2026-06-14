"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FootballLoader } from "@/components/FootballLoader";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  COUNTRY_REGIONS,
  detectBrowserTimezone,
  timezoneForCountry,
  timezoneOptions,
} from "@/lib/signupProfile";

type Profile = {
  id: number;
  username: string;
  email: string;
  country: string | null;
  timezone: string | null;
  daily_digest_opt_in: boolean;
  created_at: string | null;
};

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, logout, refreshUser } = useAuth();

  const [profile, setProfile] = useState<Profile | null>(null);
  const [loadError, setLoadError] = useState("");
  const [editing, setEditing] = useState(false);

  // Edit form state
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [country, setCountry] = useState("");
  const [timezone, setTimezone] = useState("");
  const [dailyDigest, setDailyDigest] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [savedToast, setSavedToast] = useState(false);

  // Delete modal
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleteSuccess, setDeleteSuccess] = useState(false);

  // Redirect unauthenticated users - but not during the post-delete success
  // flow, which handles its own redirect to the login page.
  useEffect(() => {
    if (!loading && !user && !deleteSuccess) {
      router.replace("/auth?next=/profile");
    }
  }, [loading, user, router, deleteSuccess]);

  const loadProfile = useCallback(async () => {
    try {
      const data = await api<Profile>("/users/me");
      setProfile(data);
      setLoadError("");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load your profile");
    }
  }, []);

  useEffect(() => {
    if (user) loadProfile();
  }, [user, loadProfile]);

  const tzOptions = useMemo(
    () => timezoneOptions(profile?.timezone ?? detectBrowserTimezone()),
    [profile?.timezone]
  );

  function startEdit() {
    if (!profile) return;
    setUsername(profile.username);
    setEmail(profile.email);
    setCountry(profile.country ?? "");
    setTimezone(profile.timezone ?? detectBrowserTimezone() ?? "UTC");
    setDailyDigest(profile.daily_digest_opt_in);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setFormError("");
    setEditing(true);
  }

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");

    const wantsPasswordChange = Boolean(newPassword || confirmPassword || currentPassword);
    if (wantsPasswordChange) {
      if (newPassword.length < 6) {
        setFormError("New password must be at least 6 characters.");
        return;
      }
      if (newPassword !== confirmPassword) {
        setFormError("New password and confirmation do not match.");
        return;
      }
      if (!currentPassword) {
        setFormError("Enter your current password to change it.");
        return;
      }
    }

    const body: Record<string, unknown> = {};
    if (profile && username !== profile.username) body.username = username;
    if (profile && email !== profile.email) body.email = email;
    // country/timezone always sent (allows clearing to a new value)
    body.country = country || null;
    body.timezone = timezone || null;
    if (profile && dailyDigest !== profile.daily_digest_opt_in) {
      body.daily_digest_opt_in = dailyDigest;
    }
    if (wantsPasswordChange) {
      body.password = newPassword;
      body.current_password = currentPassword;
    }

    setSaving(true);
    try {
      const updated = await api<Profile>("/users/me", {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      setProfile(updated);
      await refreshUser(); // keep nav/username and stored timezone in sync
      setEditing(false);
      setSavedToast(true);
      setTimeout(() => setSavedToast(false), 3000);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save changes");
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    setDeleteError("");
    if (!deletePassword) {
      setDeleteError("Enter your password to confirm.");
      return;
    }
    setDeleting(true);
    try {
      await api<void>("/users/me", {
        method: "DELETE",
        body: JSON.stringify({ password: deletePassword }),
      });
      // Show a brief success state, then clear auth and go to the login page.
      setDeleting(false);
      setDeleteSuccess(true);
      setTimeout(() => {
        logout();
        router.replace("/auth");
      }, 1400);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete account");
      setDeleting(false);
    }
  }

  if (loading || (!user && !loadError)) {
    return <FootballLoader layout="section" label="Loading your profile…" />;
  }
  if (!profile && !loadError) {
    return <FootballLoader layout="section" label="Loading your profile…" />;
  }

  return (
    <div className="auth-shell mx-auto max-w-2xl px-1">
      <h1 className="auth-title">Your profile</h1>
      <p className="auth-subtitle">Manage your account, region, and time zone.</p>

      {savedToast && (
        <p className="auth-field-hint mt-3 text-app-gold" role="status">
          Profile updated.
        </p>
      )}
      {loadError && <p className="auth-error mt-4">{loadError}</p>}

      {profile && !editing && (
        <div className="auth-card mt-6 space-y-4">
          <ProfileRow label="Display name" value={profile.username} />
          <ProfileRow label="Email" value={profile.email} />
          <ProfileRow label="Country / region" value={profile.country || "Not set"} />
          <ProfileRow label="Time zone" value={profile.timezone || "Auto (UTC)"} />
          <ProfileRow
            label="Daily digest"
            value={profile.daily_digest_opt_in ? "Subscribed" : "Off"}
          />
          <div className="flex flex-wrap gap-3 pt-2">
            <button type="button" className="btn-primary" onClick={startEdit}>
              Edit profile
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setDeleteOpen(true)}
            >
              Delete account
            </button>
          </div>
        </div>
      )}

      {profile && editing && (
        <form onSubmit={saveProfile} className="auth-card mt-6 space-y-4">
          <div>
            <label htmlFor="pf-username" className="auth-field-label">
              Display name
            </label>
            <input
              id="pf-username"
              className="auth-field-input"
              value={username}
              minLength={3}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div>
            <label htmlFor="pf-email" className="auth-field-label">
              Email
            </label>
            <input
              id="pf-email"
              type="email"
              className="auth-field-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label htmlFor="pf-country" className="auth-field-label">
              Country / region
            </label>
            <select
              id="pf-country"
              className="auth-field-input"
              value={country}
              onChange={(e) => {
                const next = e.target.value;
                setCountry(next);
                // Re-sync the time zone field to the chosen country's zone, so what
                // the user sees is what gets saved. "Other"/none keeps the current
                // zone for manual control; a later manual pick still overrides this.
                const zone = timezoneForCountry(next);
                if (zone) setTimezone(zone);
              }}
            >
              <option value="">Prefer not to say</option>
              {COUNTRY_REGIONS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="pf-timezone" className="auth-field-label">
              Time zone
            </label>
            <select
              id="pf-timezone"
              className="auth-field-input"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              {tzOptions.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
            <p className="auth-field-hint">Match kickoff times are shown in this zone.</p>
          </div>

          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={dailyDigest}
              onChange={(e) => setDailyDigest(e.target.checked)}
            />
            <span className="auth-field-label !mb-0">Email me a daily match digest</span>
          </label>

          <fieldset className="space-y-3 border-t border-white/10 pt-4">
            <legend className="auth-field-label">Change password (optional)</legend>
            <input
              type="password"
              autoComplete="current-password"
              className="auth-field-input"
              placeholder="Current password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
            <input
              type="password"
              autoComplete="new-password"
              className="auth-field-input"
              placeholder="New password (min 6 characters)"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <input
              type="password"
              autoComplete="new-password"
              className="auth-field-input"
              placeholder="Confirm new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </fieldset>

          {formError && <p className="auth-error">{formError}</p>}

          <div className="flex flex-wrap gap-3">
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setEditing(false)}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {deleteOpen && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-title"
        >
          <div className="auth-card w-full max-w-md">
            {deleteSuccess ? (
              <div role="status" aria-live="polite">
                <h2 id="delete-title" className="auth-title text-2xl">
                  Account deleted successfully
                </h2>
                <p className="mt-3 text-sm text-gray-300">
                  Your account has been removed. Redirecting you to the login page…
                </p>
              </div>
            ) : (
              <>
                <h2 id="delete-title" className="auth-title text-2xl">
                  Delete account?
                </h2>
                <p className="mt-3 text-sm text-gray-300">
                  This permanently deletes your account and all of your brackets, fan-room
                  messages, and follows. This cannot be undone. Enter your password to confirm.
                </p>
                <input
                  type="password"
                  autoComplete="current-password"
                  className="auth-field-input mt-4"
                  placeholder="Password"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                />
                {deleteError && <p className="auth-error mt-2">{deleteError}</p>}
                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="btn-primary !bg-red-600 hover:!bg-red-500"
                    onClick={confirmDelete}
                    disabled={deleting}
                  >
                    {deleting ? "Deleting…" : "Delete my account"}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      setDeleteOpen(false);
                      setDeletePassword("");
                      setDeleteError("");
                    }}
                    disabled={deleting}
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/5 pb-3 last:border-0">
      <span className="auth-field-label !mb-0">{label}</span>
      <span className="text-right text-sm text-gray-200">{value}</span>
    </div>
  );
}
