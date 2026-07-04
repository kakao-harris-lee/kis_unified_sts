import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";
import { useIndicatorCatalog } from "@/lib/builder/useIndicatorCatalog";
import type { CapabilityIndicator } from "@/lib/dashboard/strategyBuilder";

vi.mock("@/lib/dashboard/strategyBuilder", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/dashboard/strategyBuilder")>();
  return {
    ...actual,
    strategyBuilderApi: {
      ...actual.strategyBuilderApi,
      getCapabilities: vi.fn(),
    },
  };
});

import { strategyBuilderApi } from "@/lib/dashboard/strategyBuilder";

const getCapabilities = strategyBuilderApi.getCapabilities as unknown as ReturnType<typeof vi.fn>;

const liveIndicators: CapabilityIndicator[] = [
  {
    id: "rsi",
    name: "RSI",
    name_ko: "RSI",
    category: "oscillator",
    outputs: [{ id: "value", name: "값" }],
    implemented: true,
    backtest_supported: true,
    runtime_supported: true,
  },
];

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: 1, retryDelay: 0, gcTime: 0, staleTime: 0 },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children);
  };
}

describe("useIndicatorCatalog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns the constants seed immediately while the fetch is loading", () => {
    getCapabilities.mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useIndicatorCatalog(), { wrapper: makeWrapper() });
    // No blank screen: catalog is populated from constants during load.
    expect(result.current.status).toBe("loading");
    expect(result.current.getById("rsi")).toBeDefined();
    expect(result.current.all.length).toBeGreaterThan(50);
  });

  it("switches to live catalog after capabilities resolve", async () => {
    getCapabilities.mockResolvedValue({ data: { indicators: liveIndicators } });
    const { result } = renderHook(() => useIndicatorCatalog(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.status).toBe("live"));

    // rsi is backend-supported; doji (constants-only) is now backend-unsupported.
    expect(result.current.getById("rsi")?.backendUnsupported).toBe(false);
    expect(result.current.getById("doji")?.backendUnsupported).toBe(true);
    expect(getCapabilities).toHaveBeenCalledTimes(1);
  });

  it("falls back to the constants seed when the fetch fails (graceful degrade)", async () => {
    getCapabilities.mockRejectedValue(new Error("backend down"));
    const { result } = renderHook(() => useIndicatorCatalog(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.status).toBe("fallback"));

    // Still fully populated, and nothing is falsely marked backend-unsupported.
    expect(result.current.getById("rsi")).toBeDefined();
    expect(result.current.getById("doji")?.backendUnsupported).toBeFalsy();
  });
});
