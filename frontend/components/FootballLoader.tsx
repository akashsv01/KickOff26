"use client";

type FootballLoaderProps = {
  size?: "sm" | "md" | "lg";
  label?: string;
  layout?: "inline" | "section";
  className?: string;
};

const BALL_SIZE: Record<NonNullable<FootballLoaderProps["size"]>, string> = {
  sm: "text-base",
  md: "text-3xl",
  lg: "text-5xl",
};

export function FootballLoader({
  size = "md",
  label,
  layout = "inline",
  className = "",
}: FootballLoaderProps) {
  const ball = (
    <span
      className={`football-loader-ball inline-block leading-none ${BALL_SIZE[size]}`}
      aria-hidden={label ? true : undefined}
      role={label ? undefined : "status"}
      aria-label={label ? undefined : "Loading"}
    >
      ⚽
    </span>
  );

  if (layout === "section") {
    return (
      <div
        className={`flex min-h-[40vh] flex-col items-center justify-center gap-3 text-app-faint ${className}`}
        role="status"
        aria-live="polite"
      >
        {ball}
        {label ? <span className="text-sm text-app-muted">{label}</span> : null}
      </div>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-2 ${className}`}
      role="status"
      aria-live="polite"
    >
      {ball}
      {label ? <span className="text-sm text-app-muted">{label}</span> : null}
    </span>
  );
}
