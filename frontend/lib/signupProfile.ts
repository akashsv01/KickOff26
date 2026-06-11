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
  followed_team_ids?: number[];
};

export const MAX_EXTRA_FOLLOWS = 5;
