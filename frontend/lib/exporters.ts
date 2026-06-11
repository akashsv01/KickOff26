"use client";

/** Client-side export helpers (html-to-image + jsPDF, loaded lazily). */

const BRAND = {
  gold: [212, 175, 55] as const,
  goldLight: [246, 221, 142] as const,
  ink: [20, 26, 48] as const,
  paper: [250, 248, 245] as const,
  muted: [120, 113, 108] as const,
  text: [26, 26, 26] as const,
};

const JSPDF_MAX_DIM = 14000;
const EXPORT_LOG_PREFIX = "[KickOff26 export]";

export class ExportCaptureError extends Error {
  readonly stage: string;
  readonly causeDetail: string;

  constructor(stage: string, message: string, cause?: unknown) {
    const causeDetail =
      cause instanceof Error
        ? cause.message
        : cause != null
          ? String(cause)
          : "";
    super(causeDetail ? `${message}: ${causeDetail}` : message);
    this.name = "ExportCaptureError";
    this.stage = stage;
    this.causeDetail = causeDetail;
  }
}

/** Human-readable export failure for toasts (includes stage + message). */
export function formatExportError(err: unknown): string {
  if (err instanceof ExportCaptureError) {
    return `${err.stage} - ${err.message}`;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return String(err);
}

export function logExportError(context: string, err: unknown) {
  const detail = formatExportError(err);
  console.error(EXPORT_LOG_PREFIX, context, detail, err);
}

function triggerDownload(dataUrl: string, filename: string) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function waitForPaint() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

function measureNode(node: HTMLElement) {
  const width = Math.max(
    node.scrollWidth,
    node.offsetWidth,
    node.getBoundingClientRect().width,
    1
  );
  const height = Math.max(
    node.scrollHeight,
    node.offsetHeight,
    node.getBoundingClientRect().height,
    1
  );
  return { width: Math.ceil(width), height: Math.ceil(height) };
}

/** Briefly make hidden export nodes measurable (opacity:0 parents report 0×0). */
async function withMeasurableNode<T>(
  node: HTMLElement,
  fn: (dims: { width: number; height: number }) => Promise<T>
): Promise<T> {
  const chain: HTMLElement[] = [node];
  let parent = node.parentElement;
  while (parent) {
    chain.push(parent);
    parent = parent.parentElement;
  }

  const saved = chain.map((el) => ({
    el,
    cssText: el.style.cssText,
    opacity: el.style.opacity,
    visibility: el.style.visibility,
  }));

  for (const el of chain) {
    el.style.opacity = "1";
    el.style.visibility = "visible";
  }
  const mount = chain[chain.length - 1];
  mount.style.position = "fixed";
  mount.style.left = "0";
  mount.style.top = "0";
  mount.style.zIndex = "-1";
  mount.style.pointerEvents = "none";
  mount.style.overflow = "visible";

  node.style.position = "relative";
  node.style.left = "0";
  node.style.top = "0";
  node.style.transform = "translateX(-200vw)";

  await waitForPaint();
  const dims = measureNode(node);

  try {
    return await fn(dims);
  } finally {
    for (const snap of saved) {
      snap.el.style.cssText = snap.cssText;
    }
  }
}

const EXPORT_CLASS_COLORS: Record<string, string> = {
  "text-champagne": "#d4af37",
  "text-app": "#f5f0e6",
  "text-app-faint": "#78716c",
  "text-app-muted": "#a8a29e",
};

const INLINE_COLOR_PROPS = [
  "color",
  "backgroundColor",
  "borderTopColor",
  "borderRightColor",
  "borderBottomColor",
  "borderLeftColor",
  "outlineColor",
  "fill",
  "stroke",
] as const;

/** Resolve modern CSS color tokens to rgb/hex on the live tree before cloning. */
function inlineComputedColors(root: HTMLElement) {
  const win = root.ownerDocument.defaultView ?? window;
  const nodes = [root, ...Array.from(root.querySelectorAll<HTMLElement>("*"))];
  for (const el of nodes) {
    const cs = win.getComputedStyle(el);
    for (const prop of INLINE_COLOR_PROPS) {
      const val = cs[prop];
      if (val && val !== "transparent" && val !== "rgba(0, 0, 0, 0)") {
        el.style.setProperty(prop, val);
      }
    }
    el.style.backdropFilter = "none";
    el.style.setProperty("-webkit-backdrop-filter", "none");
    if (cs.backgroundImage && cs.backgroundImage !== "none") {
      const bg = cs.backgroundColor;
      if (bg && bg !== "transparent" && bg !== "rgba(0, 0, 0, 0)") {
        el.style.backgroundImage = "none";
        el.style.backgroundColor = bg;
      }
    }
  }
}

function sanitizeExportDom(root: ParentNode) {
  root.querySelectorAll<HTMLElement>("*").forEach((el) => {
    el.style.backdropFilter = "none";
    el.style.setProperty("-webkit-backdrop-filter", "none");

    for (const [cls, color] of Object.entries(EXPORT_CLASS_COLORS)) {
      if (el.classList.contains(cls)) {
        el.style.color = color;
      }
    }

    if (el.classList.contains("md-glass") && !el.classList.contains("bracket-export-root")) {
      el.style.background = "#14121c";
      el.style.border = "1px solid rgba(255, 255, 255, 0.15)";
      el.style.boxShadow = "none";
    }
  });

  root.querySelectorAll<HTMLImageElement>("img").forEach((img) => {
    if (!img.dataset.exportKeep) {
      img.removeAttribute("src");
      img.style.display = "none";
    }
  });
}

function prepareCaptureClone(node: HTMLElement, dims: { width: number; height: number }) {
  const mount = document.createElement("div");
  mount.className = "export-capture-mount";
  mount.style.cssText =
    "position:fixed;left:0;top:0;z-index:2147483646;opacity:1;visibility:visible;pointer-events:none;overflow:visible;transform:translateX(-200vw);";

  const clone = node.cloneNode(true) as HTMLElement;
  clone.style.opacity = "1";
  clone.style.visibility = "visible";
  clone.style.position = "relative";
  clone.style.left = "0";
  clone.style.top = "0";
  clone.style.transform = "none";
  clone.style.width = `${dims.width}px`;
  clone.style.height = `${dims.height}px`;
  clone.style.overflow = "visible";

  mount.appendChild(clone);
  document.body.appendChild(mount);
  return { mount, clone };
}

async function captureNode(
  node: HTMLElement,
  options?: { background?: string }
): Promise<HTMLCanvasElement> {
  const { toCanvas } = await import("html-to-image");
  const bg = options?.background ?? "#0b0a0f";
  const pixelRatio = Math.min(2, window.devicePixelRatio || 1.5);

  return withMeasurableNode(node, async (dims) => {
    inlineComputedColors(node);
    const { mount, clone } = prepareCaptureClone(node, dims);
    await waitForPaint();

    const captureWidth = Math.max(
      clone.scrollWidth,
      clone.offsetWidth,
      dims.width
    );
    const captureHeight = Math.max(
      clone.scrollHeight,
      clone.offsetHeight,
      dims.height
    );

    const root = clone.querySelector(".bracket-export-root") as HTMLElement | null;
    if (root) {
      root.style.overflow = "visible";
      root.style.width = `${captureWidth}px`;
      root.style.minHeight = `${captureHeight}px`;
    }
    sanitizeExportDom(clone);

    try {
      const canvas = await toCanvas(clone, {
        backgroundColor: bg,
        pixelRatio,
        width: captureWidth,
        height: captureHeight,
        cacheBust: true,
        style: {
          opacity: "1",
          visibility: "visible",
          transform: "none",
        },
      });

      try {
        canvas.toDataURL("image/png");
      } catch (taintErr) {
        throw new ExportCaptureError(
          "canvas taint check",
          "Capture produced a tainted image (external assets blocked export)",
          taintErr
        );
      }

      if (canvas.width < 2 || canvas.height < 2) {
        throw new ExportCaptureError(
          "empty canvas",
          `Capture returned ${canvas.width}×${canvas.height} (hidden node may have zero layout)`
        );
      }

      return canvas;
    } catch (err) {
      if (err instanceof ExportCaptureError) throw err;
      throw new ExportCaptureError("html-to-image", "Bracket capture failed", err);
    } finally {
      mount.remove();
    }
  });
}

function scaleCanvasIfNeeded(canvas: HTMLCanvasElement): HTMLCanvasElement {
  const maxDim = Math.max(canvas.width, canvas.height);
  if (maxDim <= JSPDF_MAX_DIM) return canvas;

  const ratio = JSPDF_MAX_DIM / maxDim;
  const scaled = document.createElement("canvas");
  scaled.width = Math.floor(canvas.width * ratio);
  scaled.height = Math.floor(canvas.height * ratio);
  const ctx = scaled.getContext("2d");
  if (!ctx) return canvas;
  ctx.drawImage(canvas, 0, 0, scaled.width, scaled.height);
  return scaled;
}

export async function exportNodeToPng(node: HTMLElement, filename: string) {
  await waitForPaint();
  try {
    const canvas = scaleCanvasIfNeeded(await captureNode(node));
    triggerDownload(canvas.toDataURL("image/png"), filename);
  } catch (err) {
    logExportError("PNG", err);
    throw err;
  }
}

export async function exportNodeToPdf(node: HTMLElement, filename: string) {
  await waitForPaint();
  try {
    const canvas = scaleCanvasIfNeeded(await captureNode(node));
    const { jsPDF } = await import("jspdf");
    const margin = 24;
    const pageW = canvas.width + margin * 2;
    const pageH = canvas.height + margin * 2;
    const pdf = new jsPDF({
      orientation: pageW >= pageH ? "landscape" : "portrait",
      unit: "px",
      format: [pageW, pageH],
    });
    pdf.addImage(
      canvas.toDataURL("image/png"),
      "PNG",
      margin,
      margin,
      canvas.width,
      canvas.height
    );
    pdf.save(filename);
  } catch (err) {
    logExportError("PDF", err);
    if (err instanceof ExportCaptureError) throw err;
    throw new ExportCaptureError("jsPDF", "PDF assembly failed", err);
  }
}

export type ItineraryStopExport = {
  index: number;
  city: string;
  country?: string;
  venue?: string | null;
  fixture: string;
  date?: string | null;
  ticketRange?: string | null;
  travelLeg?: string | null;
};

export type ItineraryExport = {
  title: string;
  username?: string;
  subtitle?: string;
  stops: ItineraryStopExport[];
  totals: { label: string; value: string }[];
  disclaimer: string;
  mapNode?: HTMLElement | null;
};

function setFill(pdf: import("jspdf").jsPDF, rgb: readonly [number, number, number]) {
  pdf.setFillColor(rgb[0], rgb[1], rgb[2]);
}

function setText(pdf: import("jspdf").jsPDF, rgb: readonly [number, number, number]) {
  pdf.setTextColor(rgb[0], rgb[1], rgb[2]);
}

function drawBrandHeader(
  pdf: import("jspdf").jsPDF,
  pageW: number,
  data: ItineraryExport,
  margin: number
): number {
  const headerH = 96;
  setFill(pdf, BRAND.ink);
  pdf.rect(0, 0, pageW, headerH, "F");
  setFill(pdf, BRAND.gold);
  pdf.rect(0, headerH - 3, pageW, 3, "F");

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(20);
  setText(pdf, BRAND.goldLight);
  pdf.text("KICKOFF26", margin, 34);

  pdf.setFontSize(13);
  setText(pdf, BRAND.paper);
  pdf.text("Travel Planner Itinerary", margin, 54);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(10);
  setText(pdf, [196, 190, 180]);
  const meta: string[] = [];
  if (data.username) meta.push(`Fan: ${data.username}`);
  if (data.subtitle) meta.push(data.subtitle);
  if (meta.length) pdf.text(meta.join("  ·  "), margin, 72);

  setText(pdf, BRAND.text);
  return headerH + 18;
}

function drawStopCard(
  pdf: import("jspdf").jsPDF,
  stop: ItineraryStopExport,
  margin: number,
  contentW: number,
  pageW: number,
  y: number
): number {
  const cardPad = 14;
  const lineH = 13;
  const lines: { label: string; value: string }[] = [
    { label: "Match", value: stop.fixture },
  ];
  if (stop.venue) lines.push({ label: "Venue", value: stop.venue });
  if (stop.ticketRange) lines.push({ label: "Tickets (est.)", value: stop.ticketRange });
  if (stop.travelLeg) lines.push({ label: "Travel", value: stop.travelLeg });

  let cardH = cardPad * 2 + 18 + lines.length * lineH + 8;
  if (stop.date) cardH += 14;

  setFill(pdf, BRAND.paper);
  pdf.setDrawColor(BRAND.gold[0], BRAND.gold[1], BRAND.gold[2]);
  pdf.setLineWidth(0.75);
  pdf.roundedRect(margin, y, contentW, cardH, 6, 6, "FD");

  setFill(pdf, BRAND.gold);
  pdf.circle(margin + 18, y + 22, 10, "F");
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(10);
  setText(pdf, BRAND.ink);
  pdf.text(String(stop.index), margin + 18, y + 25, { align: "center" });

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(13);
  setText(pdf, BRAND.text);
  pdf.text(stop.city, margin + 36, y + 20);
  if (stop.country && !stop.city.includes(stop.country)) {
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(10);
    setText(pdf, BRAND.muted);
    pdf.text(stop.country, margin + 36, y + 33);
  }

  if (stop.date) {
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(9);
    setText(pdf, BRAND.muted);
    pdf.text(stop.date, pageW - margin - cardPad, y + 20, { align: "right" });
  }

  let lineY = y + cardPad + 28;
  pdf.setFontSize(10);
  for (const row of lines) {
    pdf.setFont("helvetica", "bold");
    setText(pdf, BRAND.muted);
    pdf.text(`${row.label}:`, margin + cardPad, lineY);
    pdf.setFont("helvetica", "normal");
    setText(pdf, BRAND.text);
    const wrapped = pdf.splitTextToSize(row.value, contentW - cardPad * 2 - 72);
    pdf.text(wrapped, margin + cardPad + 72, lineY);
    lineY += lineH * Math.max(1, wrapped.length);
  }

  return y + cardH + 12;
}

/** Branded multi-section itinerary PDF. */
export async function exportItineraryToPdf(data: ItineraryExport, filename: string) {
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
  const pageW = pdf.internal.pageSize.getWidth();
  const pageH = pdf.internal.pageSize.getHeight();
  const margin = 40;
  const contentW = pageW - margin * 2;
  let y = drawBrandHeader(pdf, pageW, data, margin);

  const ensureSpace = (needed: number) => {
    if (y + needed > pageH - margin) {
      pdf.addPage();
      y = margin;
    }
  };

  if (data.mapNode) {
    try {
      await waitForPaint();
      const canvas = await captureNode(data.mapNode, { background: "#e8e4dc" });
      const ratio = canvas.height / canvas.width;
      const imgW = contentW;
      const imgH = Math.min(imgW * ratio, 200);
      ensureSpace(imgH + 20);
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(12);
      setText(pdf, BRAND.text);
      pdf.text("Route map", margin, y);
      y += 14;
      pdf.addImage(canvas.toDataURL("image/png"), "PNG", margin, y, imgW, imgH);
      y += imgH + 18;
    } catch (mapErr) {
      logExportError("itinerary map (best-effort)", mapErr);
    }
  }

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(12);
  setText(pdf, BRAND.text);
  ensureSpace(24);
  pdf.text("Stops", margin, y);
  y += 16;

  for (const stop of data.stops) {
    ensureSpace(120);
    y = drawStopCard(pdf, stop, margin, contentW, pageW, y);
  }

  if (data.totals.length) {
    ensureSpace(40 + data.totals.length * 16);
    y += 4;
    setFill(pdf, BRAND.ink);
    pdf.roundedRect(margin, y, contentW, 20 + data.totals.length * 16, 6, 6, "F");
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(11);
    setText(pdf, BRAND.goldLight);
    pdf.text("Trip totals", margin + 14, y + 16);
    y += 28;
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(10);
    for (const t of data.totals) {
      setText(pdf, BRAND.paper);
      pdf.text(t.label, margin + 14, y);
      pdf.text(t.value, pageW - margin - 14, y, { align: "right" });
      y += 16;
    }
    y += 10;
    setText(pdf, BRAND.text);
  }

  ensureSpace(36);
  pdf.setFont("helvetica", "italic");
  pdf.setFontSize(8);
  setText(pdf, BRAND.muted);
  const disclaimer = pdf.splitTextToSize(data.disclaimer, contentW);
  pdf.text(disclaimer, margin, y);

  pdf.save(filename);
}
