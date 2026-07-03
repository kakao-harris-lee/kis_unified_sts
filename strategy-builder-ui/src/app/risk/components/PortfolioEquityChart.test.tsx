import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import type { PortfolioEquityHistoryPoint } from "@/lib/dashboard/portfolio";
import {
  EquityCurveChart,
  MddStageChart,
  stageTransitions,
} from "./PortfolioEquityChart";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div data-testid="responsive-chart">{children}</div>
  ),
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ReferenceLine: () => null,
}));

function point(
  overrides: Partial<PortfolioEquityHistoryPoint> = {},
): PortfolioEquityHistoryPoint {
  return {
    trade_date: "2026-07-01",
    total_equity: 125_000_000,
    track_a_equity: null,
    track_b_equity: 21_875_000,
    track_c_equity: 9_375_000,
    month_start_equity: 130_000_000,
    month_peak_equity: 131_500_000,
    // 배치 발행 단위는 비율(fraction, -0.0494 = -4.94%).
    monthly_mdd_pct: -0.0494,
    stage: "NORMAL",
    mode: "shadow",
    ...overrides,
  };
}

describe("stageTransitions", () => {
  it("marks only the days where the stage changes", () => {
    const points = [
      point({ trade_date: "2026-07-01", stage: "NORMAL" }),
      point({ trade_date: "2026-07-02", stage: "NORMAL" }),
      point({ trade_date: "2026-07-03", stage: "REDUCE" }),
      point({ trade_date: "2026-07-04", stage: "REDUCE" }),
      point({ trade_date: "2026-07-07", stage: "NORMAL" }),
    ];

    expect(stageTransitions(points)).toEqual([
      { trade_date: "2026-07-03", stage: "REDUCE" },
      { trade_date: "2026-07-07", stage: "NORMAL" },
    ]);
  });

  it("skips null stages and never marks the first observed stage", () => {
    const points = [
      point({ trade_date: "2026-07-01", stage: null }),
      point({ trade_date: "2026-07-02", stage: "NORMAL" }),
      point({ trade_date: "2026-07-03", stage: "unknown-stage" }),
      point({ trade_date: "2026-07-04", stage: "HALT_NEW" }),
    ];

    expect(stageTransitions(points)).toEqual([
      { trade_date: "2026-07-04", stage: "HALT_NEW" },
    ]);
  });
});

describe("EquityCurveChart", () => {
  it("renders the chart card with the equity series", () => {
    render(<EquityCurveChart points={[point()]} />);

    expect(screen.getByText("통합 자산 곡선")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-chart")).toBeInTheDocument();
  });

  it("renders the batch-not-running empty state without points", () => {
    render(<EquityCurveChart points={[]} />);

    expect(
      screen.getByText("배치 미가동 — equity 배치 가동 후 표시됩니다"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("responsive-chart")).not.toBeInTheDocument();
  });
});

describe("MddStageChart", () => {
  it("shows the config-sourced stage thresholds in the subtitle", () => {
    render(
      <MddStageChart
        points={[point()]}
        stages={{
          mode: "shadow",
          reduce: { threshold: -0.05, new_entry_size_factor: 0.5 },
          halt_new: { threshold: -0.08 },
          full_stop: { threshold: -0.12 },
        }}
      />,
    );

    expect(screen.getByText("월간 MDD (전체 자산 기준)")).toBeInTheDocument();
    expect(
      screen.getByText("월초 대비 낙폭 % · 임계 -5% / -8% / -12%"),
    ).toBeInTheDocument();
  });

  it("falls back to the roadmap thresholds when config is unavailable", () => {
    render(<MddStageChart points={[point()]} stages={null} />);

    expect(
      screen.getByText("월초 대비 낙폭 % · 임계 -5% / -8% / -12%"),
    ).toBeInTheDocument();
  });

  it("renders the empty state when the series has no MDD values", () => {
    render(
      <MddStageChart points={[point({ monthly_mdd_pct: null })]} stages={null} />,
    );

    expect(
      screen.getByText("배치 미가동 — equity 배치 가동 후 표시됩니다"),
    ).toBeInTheDocument();
  });
});
