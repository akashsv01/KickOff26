import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "KickOff26 — 2026 Football Tournament Companion",
    short_name: "KickOff26",
    description:
      "Live scores, bracket simulator, fan travel planner, and watch-together rooms for the 2026 international football tournament.",
    start_url: "/",
    display: "standalone",
    background_color: "#08080d",
    theme_color: "#d4af37",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
