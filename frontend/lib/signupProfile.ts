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

/**
 * Country display name -> representative IANA zone. MUST mirror the backend
 * COUNTRY_TIMEZONE (backend/app/data/country_timezones.py). Multi-zone countries
 * use the capital / most-populous zone. "Other"/unlisted has no entry.
 */
export const COUNTRY_TIMEZONE: Record<string, string> = {
  "United States": "America/New_York",
  Canada: "America/Toronto",
  Mexico: "America/Mexico_City",
  Brazil: "America/Sao_Paulo",
  Australia: "Australia/Sydney",
  Indonesia: "Asia/Jakarta",
  "United Kingdom": "Europe/London",
  Argentina: "America/Argentina/Buenos_Aires",
  Germany: "Europe/Berlin",
  France: "Europe/Paris",
  Spain: "Europe/Madrid",
  Italy: "Europe/Rome",
  Netherlands: "Europe/Amsterdam",
  Portugal: "Europe/Lisbon",
  Belgium: "Europe/Brussels",
  Switzerland: "Europe/Zurich",
  Poland: "Europe/Warsaw",
  Sweden: "Europe/Stockholm",
  Norway: "Europe/Oslo",
  Denmark: "Europe/Copenhagen",
  Turkey: "Europe/Istanbul",
  "Saudi Arabia": "Asia/Riyadh",
  "United Arab Emirates": "Asia/Dubai",
  Qatar: "Asia/Qatar",
  Egypt: "Africa/Cairo",
  Morocco: "Africa/Casablanca",
  "South Africa": "Africa/Johannesburg",
  Nigeria: "Africa/Lagos",
  India: "Asia/Kolkata",
  China: "Asia/Shanghai",
  Japan: "Asia/Tokyo",
  "South Korea": "Asia/Seoul",
  Colombia: "America/Bogota",
  Chile: "America/Santiago",
};

/** Representative IANA zone for a country label, or null for "Other"/unlisted. */
export function timezoneForCountry(countryRegion: string | null | undefined): string | null {
  if (!countryRegion) return null;
  return COUNTRY_TIMEZONE[countryRegion] ?? null;
}

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
  daily_digest_opt_in?: boolean;
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
