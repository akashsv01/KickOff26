import {
  BASE1_RECT,
  BASE2_RECT,
  BOWL_D,
  HANDLE_L_D,
  HANDLE_R_D,
  RIM_RECT,
  STAR_POINTS,
  STEM_D,
} from "./trophyPaths";

function rect(r: { x: number; y: number; width: number; height: number; rx: number }) {
  return `<rect x="${r.x}" y="${r.y}" width="${r.width}" height="${r.height}" rx="${r.rx}"/>`;
}

/**
 * Returns a self-contained SVG markup string of the gold trophy.
 * @param size pixel size of the square SVG
 * @param withBackground when true, draws a premium rounded dark badge behind
 *        the trophy (for app icons / favicons that must read on any tab color)
 */
export function trophyBadgeSvg(size = 512, withBackground = true): string {
  const goldGrad = `<linearGradient id="k26-gold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f6dd8e"/>
      <stop offset="0.52" stop-color="#d4af37"/>
      <stop offset="1" stop-color="#9a6f23"/>
    </linearGradient>`;

  const bgGrad = withBackground
    ? `<linearGradient id="k26-bg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#141a30"/>
        <stop offset="1" stop-color="#070a14"/>
      </linearGradient>`
    : "";

  const bg = withBackground ? `<rect width="64" height="64" rx="14" fill="url(#k26-bg)"/>` : "";

  // Add safe-zone padding when on a badge so maskable icons aren't clipped.
  const groupOpen = withBackground
    ? `<g fill="url(#k26-gold)" transform="translate(32 33) scale(0.8) translate(-32 -33)">`
    : `<g fill="url(#k26-gold)">`;

  const trophy = `${groupOpen}
      <polygon points="${STAR_POINTS}" opacity="0.92"/>
      ${rect(RIM_RECT)}
      <path d="${BOWL_D}"/>
      <path d="${HANDLE_L_D}"/>
      <path d="${HANDLE_R_D}"/>
      <path d="${STEM_D}"/>
      ${rect(BASE1_RECT)}
      ${rect(BASE2_RECT)}
    </g>`;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 64 64"><defs>${bgGrad}${goldGrad}</defs>${bg}${trophy}</svg>`;
}
