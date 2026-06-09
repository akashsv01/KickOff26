import type { Metadata } from "next";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "KickOff26 — 2026 International Football Tournament Companion",
  description:
    "Live scores, bracket simulator, fan travel planner, and watch-together rooms for the 2026 international football tournament.",
  openGraph: {
    title: "KickOff26",
    description: "Your all-in-one companion for the 2026 international football tournament.",
    type: "website",
  },
};

const themeInitScript = `(function(){try{var t=localStorage.getItem("kickoff26-theme");document.documentElement.setAttribute("data-theme",t==="light"?"light":"dark");}catch(e){document.documentElement.setAttribute("data-theme","dark");}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
