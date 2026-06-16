"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FootballLoader } from "@/components/FootballLoader";
import { api } from "@/lib/api";

type StadiumSummary = {
  id: number;
  name: string;
  city: string | null;
  country: string | null;
  capacity: number | null;
  match_count: number;
};

function MapPinIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect width="18" height="18" x="3" y="4" rx="2" />
      <path d="M3 10h18M8 2v4M16 2v4" />
    </svg>
  );
}

function SeatsIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13A4 4 0 0 1 16 11" />
    </svg>
  );
}

export default function StadiumsPage() {
  const [stadiums, setStadiums] = useState<StadiumSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<StadiumSummary[]>("/stadiums")
      .then(setStadiums)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load stadiums"));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <div className="md-glass border-red-500/30 p-6 text-red-300">{error}</div>
      </div>
    );
  }

  if (!stadiums) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <FootballLoader layout="section" label="Loading stadiums…" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="resources-header">
        <div>
          <h1 className="md-page-title">Stadiums</h1>
          <p className="resources-sub">
            All 16 host venues across the US, Canada, and Mexico - open one to see its matches.
          </p>
        </div>
      </header>

      <div className="stadium-grid">
        {stadiums.map((s) => (
          <Link key={s.id} href={`/stadiums/${s.id}`} className="stadium-card">
            <span className="stadium-card-eyebrow">
              <MapPinIcon />
              {[s.city, s.country].filter(Boolean).join(", ") || "Venue"}
            </span>
            <span className="stadium-card-name">{s.name}</span>
            <span className="stadium-meta">
              <span className="meta-chip">
                <CalendarIcon /> {s.match_count} {s.match_count === 1 ? "match" : "matches"}
              </span>
              {s.capacity ? (
                <span className="meta-chip">
                  <SeatsIcon /> {s.capacity.toLocaleString()} seats
                </span>
              ) : null}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
