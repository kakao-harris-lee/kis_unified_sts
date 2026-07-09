import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PortfolioEquityHistoryPoint } from "@/lib/dashboard/portfolio";
import type { MarketRiskHistoryPoint } from "@/lib/dashboard/marketRisk";
import RegimeEquityChart, {
  RegimeEquitySvg,
  joinRegimeEquity,
  regimeSpans,
} from "./RegimeEquityChart";

function eq(
  date: string,
  equity: number | null,
): PortfolioEquityHistoryPoint {
  return {
    trade_date: date,
    total_equity: equity,
    track_a_equity: null,
    track_b_equity: null,
    track_c_equity: null,
    month_start_equity: null,
    month_peak_equity: null,
    monthly_mdd_pct: null,
    stage: null,
    mode: null,
  };
}

function regime(
  date: string,
  unified_regime: string | null,
): MarketRiskHistoryPoint {
  return {
    trade_date: date,
    unified_regime,
    risk_band: null,
  } as MarketRiskHistoryPoint;
}

describe("joinRegimeEquity", () => {
  it("keeps only days with equity and looks up regime by date", () => {
    const out = joinRegimeEquity(
      [eq("2026-07-01", 100), eq("2026-07-02", null), eq("2026-07-03", 110)],
      [regime("2026-07-01", "RISK_ON"), regime("2026-07-03", "RISK_OFF")],
    );
    expect(out).toEqual([
      { trade_date: "2026-07-01", total_equity: 100, regime: "RISK_ON" },
      { trade_date: "2026-07-03", total_equity: 110, regime: "RISK_OFF" },
    ]);
  });

  it("assigns null regime when no market-risk row matches", () => {
    const out = joinRegimeEquity([eq("2026-07-01", 100)], []);
    expect(out[0].regime).toBeNull();
  });
});

describe("regimeSpans", () => {
  it("merges adjacent equal regimes into contiguous spans", () => {
    const spans = regimeSpans([
      { trade_date: "d1", total_equity: 1, regime: "RISK_ON" },
      { trade_date: "d2", total_equity: 1, regime: "RISK_ON" },
      { trade_date: "d3", total_equity: 1, regime: "RISK_OFF" },
    ]);
    expect(spans).toEqual([
      { start: "d1", end: "d2", regime: "RISK_ON" },
      { start: "d3", end: "d3", regime: "RISK_OFF" },
    ]);
  });

  it("skips null-regime days", () => {
    const spans = regimeSpans([
      { trade_date: "d1", total_equity: 1, regime: null },
      { trade_date: "d2", total_equity: 1, regime: "NEUTRAL" },
    ]);
    expect(spans).toEqual([{ start: "d2", end: "d2", regime: "NEUTRAL" }]);
  });
});

describe("RegimeEquityChart", () => {
  it("renders empty state when no equity data", () => {
    const { container } = render(
      <RegimeEquityChart equity={[]} regimeHistory={[]} />,
    );
    expect(
      screen.getByText("배치 미가동 — equity·regime 배치 가동 후 표시됩니다"),
    ).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders the section title", () => {
    render(
      <RegimeEquityChart equity={[eq("2026-07-01", 100)]} regimeHistory={[]} />,
    );
    expect(screen.getByText("자산 곡선 · Regime 오버레이")).toBeInTheDocument();
  });
});

describe("RegimeEquitySvg", () => {
  it("renders equity line and regime bands", () => {
    const data = joinRegimeEquity(
      [eq("2026-07-01", 100), eq("2026-07-02", 105), eq("2026-07-03", 95)],
      [
        regime("2026-07-01", "RISK_ON"),
        regime("2026-07-02", "RISK_ON"),
        regime("2026-07-03", "RISK_OFF"),
      ],
    );
    const { container } = render(
      <RegimeEquitySvg width={400} height={256} data={data} />,
    );
    expect(container.querySelector("svg")).not.toBeNull();
    // at least one line path + regime band rects
    expect(container.querySelectorAll("path").length).toBeGreaterThan(0);
    expect(container.querySelectorAll("rect").length).toBeGreaterThan(0);
  });
});
