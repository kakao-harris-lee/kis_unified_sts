"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AuthProvider } from "@/contexts";
import { AssetClassProvider } from "@/contexts/dashboard/AssetClassContext";
import { ToastProvider } from "@/components/ui";
import type { ReactNode } from "react";

interface ProvidersProps {
  children: ReactNode;
}

// React Query + AssetClassProvider are required by the dashboard pages ported
// from the Vite SPA (2026-05-28 big-bang). Build a fresh QueryClient per
// component mount so the app survives Next.js fast-refresh in dev without
// leaking subscriptions; defaults mirror the Vite SPA configuration.
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
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AssetClassProvider>
          <ToastProvider>{children}</ToastProvider>
        </AssetClassProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default Providers;
