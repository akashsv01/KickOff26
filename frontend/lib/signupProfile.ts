export const COUNTRY_REGIONS = [
  "United States",
  "Canada",
  "Mexico",
  "United Kingdom",
  "Brazil",
  "Argentina",
  "Germany",
  "France",
  "Spain",
  "Italy",
  "Netherlands",
  "Portugal",
  "Japan",
  "South Korea",
  "Australia",
  "Other",
] as const;

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
