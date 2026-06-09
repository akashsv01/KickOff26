/**
 * KickOff26 — original championship trophy geometry.
 *
 * A sculpted modern cup with graceful curved side handles, a stepped premium
 * base, and a small star above (subtle football/championship influence).
 * Deliberately NOT a replica of any existing trophy: no globe, no figures,
 * no copyrighted silhouette. Shapes are simple so they stay crisp at 16–32px.
 *
 * All paths are authored in a 0 0 64 64 viewBox and shared by the navbar
 * component (theme-aware) and the favicon/app-icon raster generators.
 */

export const TROPHY_VIEWBOX = "0 0 64 64";

export const STAR_POINTS =
  "32,3 33.5,6.9 37.7,7.2 34.5,9.8 35.5,13.9 32,11.6 28.5,13.9 29.5,9.8 26.3,7.2 30.5,6.9";

export const BOWL_D = "M20 20 H44 L40 33 C38 39 35 42 32 42 C29 42 26 39 24 33 Z";
export const HANDLE_L_D = "M19 21 C9 22 9 35 20 38 L20 34.5 C13.5 32.5 13.5 24.5 20 23.5 Z";
export const HANDLE_R_D = "M45 21 C55 22 55 35 44 38 L44 34.5 C50.5 32.5 50.5 24.5 44 23.5 Z";
export const STEM_D = "M28 42 H36 L34.5 49 H29.5 Z";

export const RIM_RECT = { x: 18, y: 15, width: 28, height: 5, rx: 2.5 };
export const BASE1_RECT = { x: 24, y: 49, width: 16, height: 4.5, rx: 1.5 };
export const BASE2_RECT = { x: 19, y: 53.5, width: 26, height: 5.5, rx: 2 };
