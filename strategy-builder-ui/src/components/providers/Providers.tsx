"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import type { ReactNode } from "react";

interface ProvidersProps {
  children: ReactNode;
}

// Only what the one surviving screen (`/tos`) needs: a theme and a React Query
// client. Two shell-wide providers were removed with the endpoints they called
// (legacy removal L4 deleted both from services/dashboard, review-1045 r1 LOW-1
// reported them still running here):
//   - RealtimeBridge opened `/ws` and reconnected forever with backoff;
//   - AuthProvider polled `/api/auth/status` every 30s.
// `/tos` needs neither: lib/dashboard/tos.ts authenticates with the static
// X-API-Key that lib/dashboard/client.ts attaches, and it refreshes by polling
// its own query, not by a socket.
//
// Build a fresh QueryClient per component mount so the app survives Next.js
// fast-refresh in dev without leaking subscriptions.
export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    // defaultTheme="system" + enableSystem preserves the prior behavior: users
    // on OS dark still land in dark on first visit (no stored preference yet).
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}

export default Providers;
