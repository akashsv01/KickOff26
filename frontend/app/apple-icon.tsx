import { ImageResponse } from "next/og";
import { trophyBadgeSvg } from "@/lib/trophyBadge";

export const runtime = "edge";
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  const svg = trophyBadgeSvg(180, true);
  const src = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  return new ImageResponse(
    (
      <div style={{ display: "flex", width: "100%", height: "100%" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img width={180} height={180} src={src} alt="" />
      </div>
    ),
    { ...size }
  );
}
