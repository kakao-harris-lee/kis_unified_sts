/**
 * React Query hooks that wire the (previously dead) `getCapabilities()` call
 * into the builder UI.
 *
 * - `useIndicatorCapabilities()` — raw capabilities query.
 * - `useIndicatorCatalog()` — merged catalog (capabilities ⟶ constants fallback)
 *   with a `status` flag. Both `IndicatorSelector` and `useStrategyBuilder`
 *   consume this; React Query dedupes the single request by query key so there
 *   is no double fetch.
 *
 * Graceful degrade: while loading or on error the catalog still returns the
 * full `constants.ts` seed, so the picker is never blank.
 */

"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  strategyBuilderApi,
  type BuilderCapabilitiesResponse,
} from "@/lib/dashboard/strategyBuilder";
import {
  buildCatalog,
  type CatalogStatus,
  type IndicatorCatalog,
} from "@/lib/builder/indicatorCatalog";

export const BUILDER_CAPABILITIES_QUERY_KEY = ["strategy-builder", "capabilities"] as const;

export function useIndicatorCapabilities() {
  return useQuery<BuilderCapabilitiesResponse>({
    queryKey: BUILDER_CAPABILITIES_QUERY_KEY,
    queryFn: () => strategyBuilderApi.getCapabilities().then((res) => res.data),
    // Capabilities are effectively static config; refetch rarely.
    staleTime: 5 * 60_000,
    // One quick retry, then fall back to the constants seed (no blank screen).
    retry: 1,
  });
}

export function useIndicatorCatalog(): IndicatorCatalog {
  const { data, isLoading } = useIndicatorCapabilities();

  return useMemo(() => {
    const raw = data?.indicators ?? null;
    let status: CatalogStatus;
    if (raw && raw.length > 0) {
      status = "live";
    } else if (isLoading) {
      status = "loading";
    } else {
      status = "fallback";
    }
    return buildCatalog(raw, status);
  }, [data, isLoading]);
}
