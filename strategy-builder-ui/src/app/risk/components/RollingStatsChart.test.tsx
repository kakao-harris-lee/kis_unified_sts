import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PortfolioEquityHistoryPoint } from "@/lib/dashboard/portfolio";
import RollingStatsChart, {
  RollingStatsSvg,
  computeRollingStats,
} from "./RollingStatsChart";

function point(
  overrides: Partial<PortfolioEquityHistoryPoint> = {},
): PortfolioEquityHistoryPoint {
  return {
    trade_date: "2026-07-01",
    total_equity: 100_000_000,
    track_a_equity: null,
    track_b_equity: null,
    track_c_equity: null,
    month_start_equity: 100_000_000,
    month_peak_equity: 100_000_000,
    monthly_mdd_pct: 0,
    stage: "NORMAL",
    mode: "shadow",
    ...overrides,
  };
}

// Build a linear sequence of daily-dated points with given equities.
function series(equities: (number | null)[]): PortfolioEquityHistoryPoint[] {
  return equities.map((eq, i) =>
    point({
      trade_date: `2026-07-${String(i + 1).padStart(2, "0")}`,
      total_equity: eq,
    }),
  );
}

describe("computeRollingStats", () => {
  it("returns empty when fewer than window+1 valid points", () => {
    // window=3 needs >=3 returns => >=4 points
    const pts = series([100, 101, 102]);
    expect(computeRollingStats(pts, 3)).toEqual([]);
  });

  it("emits one point once the window is full and keeps rolling", () => {
    const pts = series([100, 101, 102, 103, 104]); // 4 returns, window 3 => 2 outputs
    const out = computeRollingStats(pts, 3);
    expect(out.length).toBe(2);
    expect(out[0].trade_date).toBe("2026-07-04");
    expect(out[1].trade_date).toBe("2026-07-05");
  });

  it("reports zero volatility and zero sharpe for a constant-return ramp", () => {
    // equal +1% steps => identical returns => sd=0 => sharpe defined as 0, vol 0
    const pts = series([100, 101, 102.01, 103.0301, 104.060401]);
    const out = computeRollingStats(pts, 3);
    for (const p of out) {
      expect(p.vol_pct).toBeCloseTo(0, 6);
      expect(p.sharpe).toBe(0);
    }
  });

  it("skips null/non-positive equity points without fabricating returns", () => {
    const pts = series([100, null, 110, 0, 121]);
    // valid seq: 100,110,121 => returns +10%,+10% (2 returns)
    const out = computeRollingStats(pts, 2);
    expect(out.length).toBe(1);
    expect(out[0].vol_pct).toBeCloseTo(0, 6); // identical +10% returns
  });

  it("produces a positive sharpe for a net-up noisy series", () => {
    const pts = series([100, 102, 101, 104, 103, 106, 105, 108]);
    const out = computeRollingStats(pts, 3);
    expect(out.length).toBeGreaterThan(0);
    // net upward drift => last rolling sharpe should be positive
    expect(out[out.length - 1].sharpe).toBeGreaterThan(0);
  });
});

describe("RollingStatsChart", () => {
  it("renders empty state when insufficient data", () => {
    const { container } = render(
      <RollingStatsChart points={series([100, 101])} />,
    );
    expect(
      screen.getByText("배치 미가동 — equity 배치 가동 후 표시됩니다"),
    ).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders the section title", () => {
    render(<RollingStatsChart points={series([100, 101])} />);
    expect(screen.getByText("롤링 Sharpe (20 거래일)")).toBeInTheDocument();
  });
});

describe("RollingStatsSvg", () => {
  it("renders an svg with a path at fixed dimensions", () => {
    const data = computeRollingStats(
      series([100, 102, 101, 104, 103, 106, 105, 108]),
      3,
    );
    const { container } = render(
      <RollingStatsSvg width={400} height={256} data={data} />,
    );
    expect(container.querySelector("svg")).not.toBeNull();
    expect(container.querySelectorAll("path").length).toBeGreaterThan(0);
  });
});
