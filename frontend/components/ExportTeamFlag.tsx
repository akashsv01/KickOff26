/** Capture-safe team badge for html2canvas exports (no external flag assets). */
export function ExportTeamFlag({
  code,
  size = "sm",
}: {
  code: string;
  size?: "xs" | "sm" | "md";
}) {
  const dims =
    size === "md"
      ? { w: 28, h: 18, font: 8 }
      : size === "sm"
        ? { w: 22, h: 14, font: 7 }
        : { w: 18, h: 12, font: 6 };

  return (
    <span
      aria-hidden
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: dims.w,
        height: dims.h,
        borderRadius: 3,
        border: "1px solid #d4af37",
        background: "linear-gradient(145deg, #2a3548, #1a2030)",
        color: "#f5f0e6",
        fontSize: dims.font,
        fontWeight: 800,
        letterSpacing: "0.04em",
        flexShrink: 0,
      }}
    >
      {code}
    </span>
  );
}
