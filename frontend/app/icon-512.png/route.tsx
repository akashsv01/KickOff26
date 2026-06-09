import { ImageResponse } from "next/og";
import { trophyBadgeSvg } from "@/lib/trophyBadge";

export const runtime = "edge";

export function GET() {
  const size = 512;
  const svg = trophyBadgeSvg(size, true);
  const src = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  return new ImageResponse(
    (
      <div style={{ display: "flex", width: "100%", height: "100%" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img width={size} height={size} src={src} alt="" />
      </div>
    ),
    { width: size, height: size }
  );
}
