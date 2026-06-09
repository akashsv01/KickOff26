const COUNTRY_TO_ISO: Record<string, string> = {
  USA: "us",
  Canada: "ca",
  Mexico: "mx",
};

export function CountryFlag({ country, className = "" }: { country: string; className?: string }) {
  const iso = COUNTRY_TO_ISO[country] ?? "un";
  return (
    <span
      className={`fi fi-${iso} inline-block rounded-sm shadow-sm ${className}`}
      title={country}
      aria-hidden="true"
    />
  );
}
