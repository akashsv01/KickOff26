/**
 * Tournament team code (3-letter) → ISO 3166-1 alpha-2 (or flag-icons subdivision code).
 * Country flags only - no federation crests or trademarked logos.
 */
export const TEAM_CODE_TO_ISO2: Record<string, string> = {
  MEX: "mx",
  RSA: "za",
  KOR: "kr",
  CZE: "cz",
  CAN: "ca",
  BIH: "ba",
  QAT: "qa",
  SUI: "ch",
  BRA: "br",
  MAR: "ma",
  HAI: "ht",
  SCO: "gb-sct",
  USA: "us",
  PAR: "py",
  AUS: "au",
  TUR: "tr",
  GER: "de",
  CUW: "cw",
  CIV: "ci",
  ECU: "ec",
  NED: "nl",
  JPN: "jp",
  SWE: "se",
  TUN: "tn",
  BEL: "be",
  EGY: "eg",
  IRN: "ir",
  NZL: "nz",
  ESP: "es",
  CPV: "cv",
  KSA: "sa",
  URU: "uy",
  FRA: "fr",
  IRQ: "iq",
  SEN: "sn",
  NOR: "no",
  ARG: "ar",
  ALG: "dz",
  AUT: "at",
  JOR: "jo",
  POR: "pt",
  COD: "cd",
  UZB: "uz",
  COL: "co",
  ENG: "gb-eng",
  CRO: "hr",
  GHA: "gh",
  PAN: "pa",
  // Legacy / mock codes
  JAM: "jm",
  CHI: "cl",
  PER: "pe",
  NGA: "ng",
  DEN: "dk",
  FIN: "fi",
  UAE: "ae",
  CRC: "cr",
  HON: "hn",
  SLV: "sv",
  CMR: "cm",
  SRB: "rs",
  ITA: "it",
};

/** Resolve team code to flag-icons CSS suffix (e.g. "mx", "gb-eng"), or null for unknown/placeholders. */
export function getTeamIso2(teamCode: string): string | null {
  const code = teamCode.trim().toUpperCase();
  if (!code) return null;
  return TEAM_CODE_TO_ISO2[code] ?? null;
}

export function hasTeamFlag(teamCode: string): boolean {
  return getTeamIso2(teamCode) !== null;
}
