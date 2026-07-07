import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import type { AxiosResponse } from "axios";

import UniversePage from "./page";
import { universeApi } from "@/lib/dashboard/api";
import { ToastProvider } from "@/components/ui";
import type { UniverseResponse } from "@/lib/dashboard/universe";

vi.mock("@/components/dashboard/HeaderBar", () => ({
  default: () => <header aria-label="Cockpit header">KIS Cockpit</header>,
}));

vi.mock("@/lib/dashboard/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dashboard/api")>(
    "@/lib/dashboard/api",
  );
  return {
    ...actual,
    universeApi: {
      ...actual.universeApi,
      getUniverse: vi.fn(),
      resolve: vi.fn(),
      updateOverride: vi.fn(),
      recompute: vi.fn(),
    },
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
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{ui}</ToastProvider>
    </QueryClientProvider>,
  );
}

function baseUniverse(overrides: Partial<UniverseResponse> = {}): UniverseResponse {
  return {
    asset_class: "stock",
    generated_at: "2026-07-07T09:00:00+09:00",
    key: "universe:stock",
    override_key: "universe:stock:overrides",
    audit_key: "universe:stock:audit",
    ttl_seconds: 86400,
    codes: ["005930", "000660"],
    market_data_codes: ["005930", "000660"],
    max_symbols: 40,
    rows: [
      {
        code: "005930",
        name: "삼성전자",
        active: true,
        new_entries_allowed: true,
        market_data_required: true,
        rank: null,
        score: null,
        sources: [],
        daily_indicator: "unknown",
        override: "manual_include",
        override_detail: {
          created_at: "2026-07-01T10:00:00+09:00",
          reason: null,
          name: "삼성전자",
        },
        blocked_reason: null,
      },
      {
        code: "000660",
        name: "SK하이닉스",
        active: true,
        new_entries_allowed: true,
        market_data_required: true,
        rank: 1,
        score: 0.82,
        sources: ["screener_universe"],
        daily_indicator: "available",
        override: null,
        override_detail: null,
        blocked_reason: null,
      },
    ],
    sources: [],
    overrides: { manual_include: {}, manual_exclude: {}, expired: [] },
    policy: {},
    source_keys: {},
    notes: [],
    ...overrides,
  };
}

describe("/universe page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(universeApi.getUniverse).mockResolvedValue(
      axiosResponse(baseUniverse()),
    );
    vi.mocked(universeApi.resolve).mockResolvedValue(
      axiosResponse({ code: "005930", name: "삼성전자", known: true }),
    );
  });

  it("renders My List and System Found headings, splitting rows correctly", async () => {
    renderWithQueryClient(<UniversePage />);

    expect(
      screen.getByRole("heading", { name: "My List" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "System Found" }),
    ).toBeInTheDocument();

    // Wait for the async universe fetch to resolve and rows to render.
    await screen.findByText("삼성전자");
    await screen.findByText("SK하이닉스");

    // manual_include row (삼성전자) appears; system row (SK하이닉스) does not
    // belong to My List's table — but it should show up in System Found.
    const myListSection = screen.getByRole("heading", { name: "My List" }).closest("section");
    const systemSection = screen.getByRole("heading", { name: "System Found" }).closest("section");
    expect(myListSection).not.toBeNull();
    expect(systemSection).not.toBeNull();

    expect(
      myListSection && Array.from(myListSection.querySelectorAll("td")).some((td) =>
        td.textContent?.includes("삼성전자"),
      ),
    ).toBe(true);
    expect(
      myListSection && Array.from(myListSection.querySelectorAll("td")).some((td) =>
        td.textContent?.includes("SK하이닉스"),
      ),
    ).toBe(false);
    expect(
      systemSection && Array.from(systemSection.querySelectorAll("td")).some((td) =>
        td.textContent?.includes("SK하이닉스"),
      ),
    ).toBe(true);
  });

  it("resolves a valid 6-digit code and enables Add with the resolved name shown", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<UniversePage />);

    await screen.findByRole("heading", { name: "My List" });

    const input = screen.getByPlaceholderText("005930");
    const addButton = screen.getByRole("button", { name: "추가" });
    expect(addButton).toBeDisabled();

    await user.type(input, "005930");

    await waitFor(() => expect(universeApi.resolve).toHaveBeenCalledWith("005930"));
    await waitFor(() =>
      expect(screen.getByText(/삼성전자 · 005930/)).toBeInTheDocument(),
    );
    expect(addButton).toBeEnabled();
  });

  it("keeps Add disabled and shows an error for a non-6-digit code", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<UniversePage />);

    await screen.findByRole("heading", { name: "My List" });

    const input = screen.getByPlaceholderText("005930");
    await user.type(input, "123");

    expect(screen.getByText("6자리 종목코드를 입력하세요")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "추가" })).toBeDisabled();
    expect(universeApi.resolve).not.toHaveBeenCalled();
  });

  it("calls updateOverride with a permanent include (no ttl_seconds) when Add is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(universeApi.updateOverride).mockResolvedValue(
      axiosResponse(baseUniverse()),
    );
    renderWithQueryClient(<UniversePage />);

    await screen.findByRole("heading", { name: "My List" });

    const input = screen.getByPlaceholderText("005930");
    await user.type(input, "005930");

    await waitFor(() => expect(universeApi.resolve).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole("button", { name: "추가" })).toBeEnabled());

    await user.click(screen.getByRole("button", { name: "추가" }));

    await waitFor(() =>
      expect(universeApi.updateOverride).toHaveBeenCalledWith({
        action: "include",
        symbol: "005930",
        name: "삼성전자",
        operator: "dashboard",
      }),
    );
    const payload = vi.mocked(universeApi.updateOverride).mock.calls[0][0];
    expect(payload).not.toHaveProperty("ttl_seconds");
  });

  it("still enables Add and shows the pending label for an unknown code", async () => {
    const user = userEvent.setup();
    vi.mocked(universeApi.resolve).mockResolvedValue(
      axiosResponse({ code: "999999", name: null, known: false }),
    );
    renderWithQueryClient(<UniversePage />);

    await screen.findByRole("heading", { name: "My List" });

    const input = screen.getByPlaceholderText("005930");
    await user.type(input, "999999");

    await waitFor(() => expect(universeApi.resolve).toHaveBeenCalledWith("999999"));
    await waitFor(() =>
      expect(screen.getByText(/이름 확인 예정 · 999999/)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "추가" })).toBeEnabled();
  });
});
