"use client";

import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { WebSocketProvider } from "@/lib/websocket";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <WebSocketProvider>
          <AppShell>{children}</AppShell>
        </WebSocketProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
