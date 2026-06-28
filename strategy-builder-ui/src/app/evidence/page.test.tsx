import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AxiosResponse } from "axios";
import type { ReactNode } from "react";

import EvidencePage from "./page";
import { evidenceApi } from "@/lib/dashboard/api";

vi.mock("@/components/dashboard/HeaderBar", () => ({
  default: () => <header aria-label="Cockpit header">KIS Cockpit</header>,
}));

vi.mock("@/contexts/dashboard/AssetClassContext", () => ({
  useAssetClass: () => ({
    selectedAsset: "futures",
    setSelectedAsset: vi.fn(),
  }),
}));

vi.mock("@/lib/dashboard/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dashboard/api")>(
    "@/lib/dashboard/api",
  );
  return {
    ...actual,
    evidenceApi: { getSummary: vi.fn() },
  };
});

function axiosResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: "OK",
    headers: {},
    config: { headers: {} } as AxiosResponse<T>["config"],
  };
}

function renderWithQueryClient(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("EvidencePage", () => {
  it("renders read-only evidence gaps and strategy rows", async () => {
    vi.mocked(evidenceApi.getSummary).mockResolvedValue(
      axiosResponse({
        asset_class: "futures",
        generated_at: "2026-06-28T09:30:00+09:00",
        strategies: [
          {
            strategy: "setup_c_event_reaction",
            accepted: 7,
            rejected: 2,
            paperPnl: 125000,
            backtestPaperDelta: -18000,
            status: "observe",
          },
        ],
        evidence_gaps: [
          {
            code: "NO_RUNTIME_EVIDENCE",
            severity: "warning",
            message: "No evidence report has been connected yet.",
          },
        ],
      }),
    );

    renderWithQueryClient(<EvidencePage />);

    expect(
      await screen.findByRole("heading", { name: "Evidence Summary" }),
    ).toBeInTheDocument();
    expect(evidenceApi.getSummary).toHaveBeenCalledWith("futures");
    expect(await screen.findByText("setup_c_event_reaction")).toBeInTheDocument();
    expect(screen.getByText("NO_RUNTIME_EVIDENCE")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Refresh evidence summary" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /order|live|execute/i }),
    ).not.toBeInTheDocument();
  });
});
