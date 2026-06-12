/** Signup country/region options (ISO 3166-1 alpha-2 + display name). */
export type SignupCountry = {
  code: string;
  name: string;
};

/** Major tournament-viewing markets; codes align with backend/data/broadcasters_2026.json where available. */
export const SIGNUP_COUNTRIES: SignupCountry[] = [
  { code: "US", name: "United States" },
  { code: "CA", name: "Canada" },
  { code: "MX", name: "Mexico" },
  { code: "GB", name: "United Kingdom" },
  { code: "BR", name: "Brazil" },
  { code: "AR", name: "Argentina" },
  { code: "DE", name: "Germany" },
  { code: "FR", name: "France" },
  { code: "ES", name: "Spain" },
  { code: "IT", name: "Italy" },
  { code: "NL", name: "Netherlands" },
  { code: "PT", name: "Portugal" },
  { code: "BE", name: "Belgium" },
  { code: "CH", name: "Switzerland" },
  { code: "PL", name: "Poland" },
  { code: "SE", name: "Sweden" },
  { code: "NO", name: "Norway" },
  { code: "DK", name: "Denmark" },
  { code: "TR", name: "Turkey" },
  { code: "SA", name: "Saudi Arabia" },
  { code: "AE", name: "United Arab Emirates" },
  { code: "QA", name: "Qatar" },
  { code: "EG", name: "Egypt" },
  { code: "MA", name: "Morocco" },
  { code: "ZA", name: "South Africa" },
  { code: "NG", name: "Nigeria" },
  { code: "IN", name: "India" },
  { code: "CN", name: "China" },
  { code: "ID", name: "Indonesia" },
  { code: "JP", name: "Japan" },
  { code: "KR", name: "South Korea" },
  { code: "AU", name: "Australia" },
  { code: "CO", name: "Colombia" },
  { code: "CL", name: "Chile" },
];

/** Display names for the signup dropdown (stored in user.country_region). */
export const COUNTRY_REGIONS = [...SIGNUP_COUNTRIES.map((c) => c.name), "Other"] as const;

const ISO_BY_NAME = Object.fromEntries(SIGNUP_COUNTRIES.map((c) => [c.name, c.code]));

/** Resolve a stored country_region label to ISO 3166-1 alpha-2 (for broadcaster personalization). */
export function countryRegionToIso(countryRegion: string | null | undefined): string | null {
  if (!countryRegion || countryRegion === "Other") return null;
  return ISO_BY_NAME[countryRegion] ?? null;
}

export const PREFERRED_LANGUAGES = [
  { value: "", label: "No preference" },
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "pt", label: "Portuguese" },
  { value: "ar", label: "Arabic" },
  { value: "zh", label: "Chinese" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "it", label: "Italian" },
  { value: "nl", label: "Dutch" },
] as const;

export type RegisterProfile = {
  favorite_team_id: number;
  country_region?: string;
  preferred_language?: string;
  timezone?: string;
  followed_team_ids?: number[];
};

export const MAX_EXTRA_FOLLOWS = 5;

/** Browser IANA timezone (e.g. "Europe/London"), or null if unavailable. */
export function detectBrowserTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

/** Curated fallback list (covers every signup-country zone) for older browsers. */
const FALLBACK_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Toronto",
  "America/Mexico_City",
  "America/Bogota",
  "America/Sao_Paulo",
  "America/Argentina/Buenos_Aires",
  "America/Santiago",
  "Europe/London",
  "Europe/Lisbon",
  "Europe/Madrid",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Amsterdam",
  "Europe/Brussels",
  "Europe/Zurich",
  "Europe/Rome",
  "Europe/Warsaw",
  "Europe/Stockholm",
  "Europe/Oslo",
  "Europe/Copenhagen",
  "Europe/Istanbul",
  "Africa/Casablanca",
  "Africa/Lagos",
  "Africa/Cairo",
  "Africa/Johannesburg",
  "Asia/Riyadh",
  "Asia/Qatar",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Jakarta",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Australia/Sydney",
];

/**
 * Full IANA timezone list for the profile dropdown. Uses the browser's
 * Intl.supportedValuesOf("timeZone") when available, else a curated fallback.
 * `current` is always included so a stored value never disappears.
 */
export function timezoneOptions(current?: string | null): string[] {
  let zones: string[] = FALLBACK_TIMEZONES;
  try {
    const supported = (
      Intl as unknown as { supportedValuesOf?: (k: string) => string[] }
    ).supportedValuesOf?.("timeZone");
    if (supported && supported.length) zones = supported;
  } catch {
    /* keep fallback */
  }
  const set = new Set(zones);
  if (current) set.add(current);
  return Array.from(set).sort();
}
