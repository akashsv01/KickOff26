"use client";

import { ExportTeamFlag } from "@/components/ExportTeamFlag";
import { KnockoutBracket } from "@/components/bracket/KnockoutBracket";
import { forwardRef } from "react";

type KnockoutRound = {
  id: string;
  label: string;
  slots: { slot: string; label: string }[];
};

type BracketExportSheetProps = {
  username: string;
  championCode: string;
  championName?: string;
  rounds: KnockoutRound[];
  picks: Record<string, string>;
  slotTeams: Record<string, string>;
};

/** Off-screen, html2canvas-friendly bracket layout with solid colors (no glass/backdrop-filter). */
export const BracketExportSheet = forwardRef<HTMLDivElement, BracketExportSheetProps>(
  function BracketExportSheet(
    { username, championCode, championName, rounds, picks, slotTeams },
    ref
  ) {
    const generated = new Date().toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });

    return (
      <div
        ref={ref}
        className="bracket-export-root"
        style={{
          width: "max-content",
          minWidth: 1180,
          padding: 32,
          background: "#0b0a0f",
          color: "#f5f0e6",
          fontFamily: "system-ui, Segoe UI, sans-serif",
        }}
      >
        <header
          style={{
            borderBottom: "2px solid #d4af37",
            paddingBottom: 16,
            marginBottom: 20,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: "linear-gradient(145deg, #f6dd8e, #9a6f23)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 800,
                color: "#141a30",
                fontSize: 14,
              }}
            >
              K26
            </div>
            <div>
              <p
                style={{
                  margin: 0,
                  fontSize: 22,
                  fontWeight: 800,
                  letterSpacing: "0.06em",
                  color: "#d4af37",
                }}
              >
                KICKOFF26
              </p>
              <p style={{ margin: "2px 0 0", fontSize: 13, color: "#a8a29e" }}>
                Predicted Knockout Bracket
              </p>
            </div>
          </div>
          <div
            style={{
              marginTop: 12,
              display: "flex",
              justifyContent: "space-between",
              fontSize: 12,
              color: "#c4bdb0",
            }}
          >
            <span>Fan: {username}</span>
            <span>{generated}</span>
          </div>
        </header>

        {championCode ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 20,
              padding: "12px 16px",
              borderRadius: 12,
              border: "1px solid rgba(212, 175, 55, 0.55)",
              background: "rgba(212, 175, 55, 0.12)",
            }}
          >
            <ExportTeamFlag code={championCode} size="md" />
            <div>
              <p
                style={{
                  margin: 0,
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.15em",
                  color: "#d4af37",
                  textTransform: "uppercase",
                }}
              >
                Champion
              </p>
              <p style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 700 }}>
                {championName || championCode}
              </p>
              <p style={{ margin: "2px 0 0", fontSize: 11, color: "#a8a29e" }}>{championCode}</p>
            </div>
          </div>
        ) : null}

        <div style={{ overflow: "visible" }}>
          <KnockoutBracket
            rounds={rounds}
            picks={picks}
            slotTeams={slotTeams}
            onPick={() => {}}
            readOnly
            exportMode
          />
        </div>
      </div>
    );
  }
);
