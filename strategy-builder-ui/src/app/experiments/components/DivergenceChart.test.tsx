import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DivergencePoint } from "@/lib/api/experiments";
import DivergenceChart, { DivergenceSvg } from "./DivergenceChart";

const pts: DivergencePoint[] = [
  { trade_date: "2026-07-01", backtest_cum_pct: 0, paper_cum_pct: 0, divergence_pct: 0 },
  { trade_date: "2026-07-02", backtest_cum_pct: 10, paper_cum_pct: 5, divergence_pct: -5 },
  { trade_date: "2026-07-03", backtest_cum_pct: 21, paper_cum_pct: 8, divergence_pct: -13 },
];

describe("DivergenceChart", () => {
  it("shows no-report empty state", () => {
    render(<DivergenceChart points={[]} status="no_report" />);
    expect(
      screen.getByText(/백테스트 리포트 없음/),
    ).toBeInTheDocument();
  });

  it("shows insufficient-data empty state", () => {
    render(<DivergenceChart points={[]} status="insufficient_data" />);
    expect(screen.getByText(/겹치는 페이퍼·백테스트 구간 없음/)).toBeInTheDocument();
  });

  it("renders the latest divergence delta", () => {
    render(<DivergenceChart points={pts} status="ok" />);
    expect(screen.getByText(/-13.0%/)).toBeInTheDocument();
  });
});

describe("DivergenceSvg", () => {
  it("renders two line paths at fixed dimensions", () => {
    const { container } = render(
      <DivergenceSvg width={400} height={256} points={pts} />,
    );
    expect(container.querySelector("svg")).not.toBeNull();
    // backtest + paper lines
    expect(container.querySelectorAll("path").length).toBeGreaterThanOrEqual(2);
  });
});
