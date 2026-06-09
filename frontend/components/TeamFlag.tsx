import { getTeamIso2 } from "@/lib/flags";

const SIZE_CLASS = {
  xs: "h-3 w-4 text-xs",
  sm: "h-3.5 w-5",
  md: "h-4 w-6",
  lg: "h-6 w-8",
} as const;

type TeamFlagProps = {
  code: string;
  size?: keyof typeof SIZE_CLASS;
  className?: string;
  title?: string;
};

/** License-safe country flag via flag-icons (MIT). */
export function TeamFlag({ code, size = "sm", className = "", title }: TeamFlagProps) {
  const iso = getTeamIso2(code);
  const dim = SIZE_CLASS[size];

  if (!iso) {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded-sm border border-[color:var(--app-border)] bg-[color:var(--md-surface)] text-[9px] font-medium text-app-muted ${dim} ${className}`}
        title={title ?? code}
        aria-hidden
      >
        ?
      </span>
    );
  }

  return (
    <span
      className={`fi fi-${iso} inline-block shrink-0 overflow-hidden rounded-sm bg-cover bg-center shadow-sm ${dim} ${className}`}
      title={title ?? code}
      role="img"
      aria-label={`${code} flag`}
    />
  );
}
