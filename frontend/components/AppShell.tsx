"use client";

import { Atmosphere } from "@/components/Atmosphere";
import Nav from "@/components/Nav";
import { MatchDayNotificationsProvider } from "@/lib/matchday-notifications";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <MatchDayNotificationsProvider>
      <div className="app-canvas">
        <Atmosphere />
        <Nav />
        <main className="relative z-0 mx-auto min-h-screen max-w-7xl px-4 py-8">{children}</main>
      </div>
    </MatchDayNotificationsProvider>
  );
}
