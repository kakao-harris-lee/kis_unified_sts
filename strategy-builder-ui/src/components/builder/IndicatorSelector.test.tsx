import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { IndicatorSelector } from "./IndicatorSelector";
import type { BuilderIndicator } from "@/types/builder";
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

// macd = fully supported (unambiguous search term); sma = implemented:false
// (지원 예정, 추가 차단). engulfing (candlestick) is intentionally absent from
// capabilities → "백엔드 미지원" (선택 가능).
const capabilities: CapabilityIndicator[] = [
  {
    id: "macd",
    name: "MACD",
    name_ko: "MACD",
    category: "oscillator",
    params: [{ name: "fast", type: "number", default: 12 }],
    outputs: [{ id: "value", name: "MACD" }],
    implemented: true,
    backtest_supported: true,
    runtime_supported: true,
  },
  {
    id: "sma",
    name: "Simple Moving Average",
    name_ko: "단순 이동평균",
    category: "moving_average",
    params: [{ name: "period", type: "number", default: 20 }],
    outputs: [{ id: "value", name: "값" }],
    implemented: false,
    backtest_supported: true,
    runtime_supported: true,
  },
];

function renderSelector() {
  const onAddIndicator = vi.fn();
  const createIndicator = vi.fn((indicatorId: string): BuilderIndicator => ({
    id: `${indicatorId}_x`,
    indicatorId,
    alias: `${indicatorId}_1`,
    params: {},
    output: "value",
  }));

  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });

  render(
    createElement(
      QueryClientProvider,
      { client },
      createElement(IndicatorSelector, {
        selectedIndicators: [],
        onAddIndicator,
        onUpdateIndicator: vi.fn(),
        onRemoveIndicator: vi.fn(),
        createIndicator,
        assetClass: "stock",
      }),
    ),
  );

  return { onAddIndicator, createIndicator };
}

describe("IndicatorSelector — capability-driven badges", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCapabilities.mockResolvedValue({ data: { indicators: capabilities } });
  });

  it("blocks unimplemented indicators with a 지원 예정 badge + disabled add", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(screen.getByRole("button", { name: "지표 추가" }));
    await user.type(screen.getByLabelText("지표 검색"), "sma");

    // waits for the capabilities query to resolve and re-render.
    await screen.findByText("지원 예정");
    const smaButton = screen.getByRole("button", { name: /단순 이동평균/ });
    expect(smaButton).toBeDisabled();
  });

  it("flags backend-missing candlesticks as 백엔드 미지원 but keeps them selectable", async () => {
    const user = userEvent.setup();
    const { onAddIndicator, createIndicator } = renderSelector();

    await user.click(screen.getByRole("button", { name: "지표 추가" }));
    await user.type(screen.getByLabelText("지표 검색"), "engulfing");

    await screen.findByText("백엔드 미지원");
    const engulfingButton = screen.getByRole("button", { name: /장악형/ });
    expect(engulfingButton).not.toBeDisabled();

    await user.click(engulfingButton);
    expect(createIndicator).toHaveBeenCalledWith("engulfing");
    expect(onAddIndicator).toHaveBeenCalledTimes(1);
  });

  it("shows supported indicators without any 미지원 badge", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(screen.getByRole("button", { name: "지표 추가" }));
    await user.type(screen.getByLabelText("지표 검색"), "macd");

    const macdButton = await screen.findByRole("button", { name: /MACD/ });
    expect(macdButton).not.toBeDisabled();
    expect(macdButton).not.toHaveTextContent("미지원");
    expect(macdButton).not.toHaveTextContent("지원 예정");
  });
});
