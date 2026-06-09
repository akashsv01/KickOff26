"use client";

import { usePathname } from "next/navigation";

type Intensity = "low" | "medium" | "medium-high" | "high";

function intensityForPath(pathname: string): Intensity {
  if (pathname === "/") return "high";
  if (pathname.startsWith("/watch")) return "medium-high";
  if (pathname.startsWith("/matchday")) return "medium-high";
  // Bracket, FanPlan, Following, Account/Login and everything else → low
  return "low";
}

/**
 * Shared, non-interactive World Cup atmosphere rendered fixed behind all
 * content. Purely visual — pointer-events: none and z-index below the app.
 */
export function Atmosphere() {
  const pathname = usePathname();
  const intensity = intensityForPath(pathname || "/");

  return (
    <div className="atmos" data-intensity={intensity} aria-hidden="true">
      {/* Layer 1 — foundation */}
      <div className="atmos-foundation" />

      {/* Layer 2 — ambient color washes */}
      <div className="atmos-washes" />

      {/* Layer 4 — floodlights */}
      <div className="atmos-floodlights" />

      {/* Layer 5 — pitch geometry */}
      <div className="atmos-pitch">
        <svg
          viewBox="0 0 1440 900"
          preserveAspectRatio="xMidYMid slice"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          {/* halfway line */}
          <line x1="720" y1="120" x2="720" y2="780" />
          {/* center circle + spot */}
          <circle cx="720" cy="450" r="150" />
          <circle cx="720" cy="450" r="3" fill="currentColor" stroke="none" />
          {/* outer pitch frame */}
          <rect x="180" y="120" width="1080" height="660" rx="6" />
          {/* penalty boxes */}
          <rect x="180" y="300" width="160" height="300" />
          <rect x="1100" y="300" width="160" height="300" />
          {/* faint tactical grid */}
          <line x1="450" y1="120" x2="450" y2="780" strokeOpacity="0.5" />
          <line x1="990" y1="120" x2="990" y2="780" strokeOpacity="0.5" />
          <line x1="180" y1="450" x2="1260" y2="450" strokeOpacity="0.5" />
        </svg>
      </div>

      {/* Layer 3 — stadium silhouette */}
      <div className="atmos-stadium">
        <svg
          viewBox="0 0 1440 640"
          preserveAspectRatio="xMidYMax slice"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        >
          {/* sweeping roof arcs over the bowl */}
          <path d="M30 400 Q720 70 1410 400" strokeOpacity="0.85" />
          <path d="M110 360 Q720 110 1330 360" strokeOpacity="0.6" strokeWidth="2" />
          {/* outer bowl rim */}
          <path d="M40 460 Q720 285 1400 460" strokeOpacity="0.95" strokeWidth="3" />
          {/* filled lower bowl body, fading down */}
          <path
            d="M40 460 Q720 575 1400 460 L1400 640 L40 640 Z"
            fill="currentColor"
            fillOpacity="0.32"
            stroke="none"
          />
          {/* upper tier rim */}
          <path d="M150 505 Q720 360 1290 505" strokeOpacity="0.7" />
          {/* lower tier rim */}
          <path d="M300 560 Q720 455 1140 560" strokeOpacity="0.5" />
          {/* vertical aisle hints */}
          <g strokeOpacity="0.32" strokeWidth="1.5">
            <line x1="420" y1="500" x2="430" y2="600" />
            <line x1="620" y1="470" x2="624" y2="600" />
            <line x1="820" y1="470" x2="816" y2="600" />
            <line x1="1020" y1="500" x2="1010" y2="600" />
          </g>
          {/* floodlight towers + light banks */}
          <g strokeOpacity="0.9">
            <line x1="170" y1="455" x2="135" y2="120" strokeWidth="3" />
            <rect x="86" y="86" width="104" height="46" rx="6" fill="currentColor" fillOpacity="0.45" />
            <line x1="1270" y1="455" x2="1305" y2="120" strokeWidth="3" />
            <rect x="1250" y="86" width="104" height="46" rx="6" fill="currentColor" fillOpacity="0.45" />
          </g>
        </svg>
      </div>

      {/* Layer 6 — grain texture */}
      <div className="atmos-noise" />

      {/* Layer 7 — floating particles */}
      <div className="atmos-particles">
        <span className="atmos-particle" />
        <span className="atmos-particle" />
        <span className="atmos-particle" />
        <span className="atmos-particle" />
        <span className="atmos-particle" />
        <span className="atmos-particle" />
      </div>
    </div>
  );
}
