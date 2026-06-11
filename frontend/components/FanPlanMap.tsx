"use client";

import { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

export type FanPlanStop = {
  city: string;
  country: string;
  match_label: string;
  stadium: string;
  kickoff_at?: string | null;
  lat: number;
  lng: number;
  travel_from_prev_km?: number | null;
  travel_from_prev_hours?: number | null;
  ticket_estimate: {
    low_usd: number;
    high_usd: number;
    label: string;
    display_range: string;
    is_estimate: boolean;
  };
  cross_border_note?: string | null;
};

const ROUTE_COLOR = "#C9A227";

function numberedMarkerIcon(n: number): L.DivIcon {
  return L.divIcon({
    className: "fanplan-map-marker-wrap",
    html: `<div class="fanplan-map-marker" aria-label="Stop ${n}">${n}</div>`,
    iconSize: [44, 44],
    iconAnchor: [22, 22],
    popupAnchor: [0, -24],
  });
}

function FitRouteBounds({ stops }: { stops: FanPlanStop[] }) {
  const map = useMap();
  const positions = useMemo(
    () => stops.map((s) => [s.lat, s.lng] as [number, number]),
    [stops]
  );

  useEffect(() => {
    if (positions.length === 0) return;
    if (positions.length === 1) {
      map.setView(positions[0], 6);
      return;
    }
    map.fitBounds(L.latLngBounds(positions), { padding: [56, 56], maxZoom: 7 });
  }, [map, positions]);

  return null;
}

function formatKickoff(iso: string | null | undefined): string {
  if (!iso) return "Date TBD";
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function FanPlanMap({ stops }: { stops: FanPlanStop[] }) {
  if (stops.length === 0) return null;

  const route: [number, number][] = stops.map((s) => [s.lat, s.lng]);
  const center: [number, number] = [stops[0].lat, stops[0].lng];

  return (
    <div className="md-glass fanplan-panel fanplan-map-shell overflow-hidden">
      <div className="fanplan-map-header">
        <div>
          <p className="fanplan-kicker">Route map</p>
          <h3 className="md-section-title">Your city-hopping path</h3>
        </div>
        <div className="fanplan-map-legend" aria-label="Map legend">
          {stops.map((s, i) => (
            <span key={i} className="fanplan-map-legend-item">
              <span className="fanplan-map-legend-num">{i + 1}</span>
              {s.city}
            </span>
          ))}
        </div>
      </div>
      <div className="fanplan-map-frame">
        <MapContainer center={center} zoom={4} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitRouteBounds stops={stops} />
          {stops.map((s, i) => (
            <Marker
              key={`${s.match_label}-${i}`}
              position={[s.lat, s.lng]}
              icon={numberedMarkerIcon(i + 1)}
            >
              <Popup className="fanplan-map-popup">
                <strong>
                  Stop {i + 1} · {s.city}, {s.country}
                </strong>
                <br />
                {s.match_label}
                <br />
                {s.stadium}
                <br />
                {formatKickoff(s.kickoff_at)}
                <br />
                {s.ticket_estimate?.display_range ? (
                  <>
                    <span style={{ color: ROUTE_COLOR }}>{s.ticket_estimate.display_range}</span>
                    <br />
                    <span style={{ fontSize: "11px", opacity: 0.85 }}>Estimated pricing</span>
                  </>
                ) : null}
              </Popup>
            </Marker>
          ))}
          {route.length > 1 ? (
            <Polyline
              positions={route}
              pathOptions={{
                color: ROUTE_COLOR,
                weight: 4,
                opacity: 0.85,
                dashArray: "10 8",
                lineCap: "round",
              }}
            />
          ) : null}
        </MapContainer>
      </div>
    </div>
  );
}
