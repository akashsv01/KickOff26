"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { api } from "@/lib/api";
import {
  formatKickoff,
  localTodayKey,
  matchDateKey,
  type Match,
} from "@/lib/matchday";
import { useDisplayTimezone } from "@/lib/timezone";

/* ----------------------------------------------------------------- */
/* Animated count-up (respects prefers-reduced-motion)               */
/* ----------------------------------------------------------------- */
function useCountUp(target: number, durationMs = 1400, start = true) {
  const [value, setValue] = useState(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    if (!start) return;
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setValue(target);
      return;
    }
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / durationMs);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(eased * target));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [target, durationMs, start]);

  return value;
}

function Stat({
  target,
  label,
  accent,
  delayClass,
}: {
  target: number;
  label: string;
  accent: string;
  delayClass: string;
}) {
  const value = useCountUp(target);
  return (
    <div
      className={`home-stat home-enter ${delayClass}`}
      style={{ "--stat-accent": accent } as CSSProperties}
    >
      <div className="home-stat-value">{value}</div>
      <div className="home-stat-label">{label}</div>
    </div>
  );
}

/* ----------------------------------------------------------------- */
/* Feature destination icons (inline SVG)                            */
/* ----------------------------------------------------------------- */
const icons = {
  matchday: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12h3l2-6 4 12 2-6h7" />
    </svg>
  ),
  bracket: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 5h5v6H4M4 13h5v6H4M9 8h4v8h4M17 12h3" />
    </svg>
  ),
  fanplan: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11Z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  ),
  watch: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 11.5a8.5 8.5 0 0 1-12.2 7.7L3 21l1.8-5.8A8.5 8.5 0 1 1 21 11.5Z" />
      <path d="M8.5 11.5h.01M12 11.5h.01M15.5 11.5h.01" />
    </svg>
  ),
};

const destinations = [
  {
    href: "/matchday",
    cls: "home-dest-matchday",
    icon: icons.matchday,
    title: "Live Matches",
    desc: "Live scores with a win-probability engine and your personalized following feed.",
  },
  {
    href: "/standings",
    cls: "home-dest-standings",
    icon: icons.bracket,
    title: "Standings",
    desc: "Live group tables for all 12 groups with the top-2 plus best-8-thirds highlighted.",
  },
  {
    href: "/teams",
    cls: "home-dest-teams",
    icon: icons.matchday,
    title: "Teams & Stats",
    desc: "All 48 nations by group, with flags, team codes, and fixtures from the live data feed.",
  },
  {
    href: "/bracket",
    cls: "home-dest-bracket",
    icon: icons.bracket,
    title: "Predictions",
    desc: "Make manual picks or run a Monte Carlo simulation, then export your bracket to share.",
  },
  {
    href: "/fanplan",
    cls: "home-dest-fanplan",
    icon: icons.fanplan,
    title: "Travel Planner",
    desc: "Optimize a city-hopping itinerary across the 16 host cities and export it to PDF.",
  },
  {
    href: "/watch",
    cls: "home-dest-watch",
    icon: icons.watch,
    title: "Fan Rooms",
    desc: "Real-time rooms with live chat, custom polls, and broadcast emoji reactions.",
  },
];

const Arrow = () => (
  <svg className="home-cta-arrow" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

const SmallArrow = () => (
  <svg className="home-dest-cta-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export default function HomePage() {
  const zone = useDisplayTimezone();
  const [matches, setMatches] = useState<Match[] | null>(null);

  useEffect(() => {
    let active = true;
    api<Match[]>("/matchday/matches")
      .then((m) => {
        if (active) setMatches(m);
      })
      .catch(() => {
        if (active) setMatches([]);
      });
    return () => {
      active = false;
    };
  }, []);

  const hasData = matches !== null && matches.length > 0;
  const liveCount = hasData ? matches!.filter((m) => m.status === "live").length : 0;

  const todayKey = localTodayKey();
  const todayCount = hasData
    ? matches!.filter((m) => matchDateKey(m) === todayKey).length
    : 0;

  const nextFixture = hasData
    ? matches!
        .filter((m) => m.status !== "live" && m.status !== "finished" && m.kickoff_at)
        .filter((m) => new Date(m.kickoff_at as string).getTime() >= Date.now())
        .sort((a, b) => (a.kickoff_at ?? "").localeCompare(b.kickoff_at ?? ""))[0] ?? null
    : null;

  return (
    <div className="home">
      {/* HERO */}
      <section className="home-hero home-enter home-enter-1" aria-label="KickOff26 - World Cup 2026 companion">
        <div className="home-hero-inner">
          <span className="home-hero-kicker">
            <span className="home-hero-kicker-dot" aria-hidden />
            World Cup 2026
          </span>
          <h1 className="home-hero-title">
            Kick<span className="home-hero-title-accent">Off26</span>
          </h1>
          <p className="home-hero-sub">
            <b>Follow every match. Predict every bracket. Plan every trip. Watch together.</b>
            <br />
            Your all-in-one companion for the 2026 tournament across the United States, Canada,
            and Mexico.
          </p>
          <div className="home-hero-ctas">
            <Link href="/matchday" className="home-cta home-cta-primary">
              Explore Live Matches <Arrow />
            </Link>
            <Link href="/bracket" className="home-cta home-cta-secondary">
              Build Your Bracket
            </Link>
          </div>
        </div>
      </section>

      {/* LIVE TOURNAMENT STRIP - real data only */}
      {hasData && (
        <section className="home-enter home-enter-2" aria-label="Tournament status">
          <div className="home-live-strip">
            <div className="home-live-item">
              <span className="home-live-item-label">
                {liveCount > 0 && <span className="home-live-dot" aria-hidden />}
                Live now
              </span>
              <span className={`home-live-item-value${liveCount > 0 ? " is-live" : ""}`}>
                {liveCount > 0 ? `${liveCount} in play` : "No live matches"}
              </span>
              <span className="home-live-item-meta">
                {liveCount > 0 ? "Tap Live Matches to follow along" : "Check back at kickoff"}
              </span>
            </div>

            {nextFixture && (
              <div className="home-live-item">
                <span className="home-live-item-label">Next kickoff</span>
                <span className="home-live-item-value">
                  {nextFixture.home_team?.code} v {nextFixture.away_team?.code}
                </span>
                <span className="home-live-item-meta">
                  {formatKickoff(nextFixture.kickoff_at, zone)}
                  {nextFixture.city ? ` · ${nextFixture.city}` : ""}
                </span>
              </div>
            )}

            <div className="home-live-item">
              <span className="home-live-item-label">Today</span>
              <span className="home-live-item-value">
                {todayCount > 0 ? `${todayCount} ${todayCount === 1 ? "match" : "matches"}` : "Rest day"}
              </span>
              <span className="home-live-item-meta">
                {todayCount > 0 ? "Scheduled today" : "No fixtures today"}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* TOURNAMENT STATS */}
      <section className="home-enter home-enter-2" aria-label="Tournament at a glance">
        <div className="home-section-head">
          <span className="home-section-eyebrow">The Tournament</span>
          <h2 className="home-section-title">The biggest World Cup ever</h2>
        </div>
        <div className="home-stats">
          <Stat target={48} label="Teams" accent="var(--app-gold-subtle)" delayClass="home-enter-1" />
          <Stat target={16} label="Host Cities" accent="var(--host-mx-subtle)" delayClass="home-enter-2" />
          <Stat target={3} label="Nations" accent="var(--host-us-subtle)" delayClass="home-enter-3" />
          <Stat target={104} label="Matches" accent="var(--host-ca-subtle)" delayClass="home-enter-4" />
        </div>
      </section>

      {/* FEATURE DESTINATIONS */}
      <section className="home-enter home-enter-3" aria-label="Explore KickOff26">
        <div className="home-section-head">
          <span className="home-section-eyebrow">Explore</span>
          <h2 className="home-section-title">Four ways to live the World Cup</h2>
        </div>
        <div className="home-destinations">
          {destinations.map((d) => (
            <Link key={d.href} href={d.href} className={`home-dest ${d.cls}`}>
              <span className="home-dest-icon" aria-hidden>
                {d.icon}
              </span>
              <div className="home-dest-body">
                <h3 className="home-dest-title">{d.title}</h3>
                <p className="home-dest-desc">{d.desc}</p>
              </div>
              <span className="home-dest-cta">
                Open <SmallArrow />
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
