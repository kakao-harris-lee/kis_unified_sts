"use client";

import { useWebSocketInvalidation } from "@/hooks/dashboard/useWebSocket";

/**
 * Mounts the single `/ws` subscription that invalidates React Query caches on
 * live trading events (positions / signals / fills / data-freshness /
 * kill-switch). Renders nothing.
 *
 * Must live UNDER `QueryClientProvider` so `useWebSocketInvalidation()`'s
 * internal `useQueryClient()` resolves the app's client. Without this component
 * the hook is never mounted, the browser never opens `/ws`, and the dashboard
 * falls back to polling only (the S1a defect this fixes).
 */
export function RealtimeBridge() {
  useWebSocketInvalidation();
  return null;
}

export default RealtimeBridge;
