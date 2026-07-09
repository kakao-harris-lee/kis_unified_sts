import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PortfolioEquityHistoryPoint } from "@/lib/dashboard/portfolio";
import UnderwaterChart, {
  DrawdownSvg,
  computeDrawdown,
} from "./UnderwaterChart";

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

describe("computeDrawdown", () => {
  it("returns empty array when all equity is null", () => {
    const pts = [
      point({ trade_date: "2026-07-01", total_equity: null }),
      point({ trade_date: "2026-07-02", total_equity: null }),
    ];
    expect(computeDrawdown(pts)).toEqual([]);
  });

  it("single point is at 0% drawdown (it is its own peak)", () => {
    const result = computeDrawdown([
      point({ trade_date: "2026-07-01", total_equity: 100 }),
    ]);
    expect(result).toEqual([{ trade_date: "2026-07-01", drawdown_pct: 0 }]);
  });

  it("computes peak -> trough -> partial recovery correctly", () => {
    const result = computeDrawdown([
      point({ trade_date: "2026-07-01", total_equity: 100 }), // peak 100 -> 0%
      point({ trade_date: "2026-07-02", total_equity: 80 }), //  peak 100 -> -20%
      point({ trade_date: "2026-07-03", total_equity: 90 }), //  peak 100 -> -10%
      point({ trade_date: "2026-07-04", total_equity: 120 }), // new peak -> 0%
      point({ trade_date: "2026-07-05", total_equity: 108 }), // peak 120 -> -10%
    ]);
    expect(result.map((d) => d.drawdown_pct)).toEqual([0, -20, -10, 0, -10]);
  });

  it("drawdown is never positive", () => {
    const result = computeDrawdown([
      point({ trade_date: "2026-07-01", total_equity: 100 }),
      point({ trade_date: "2026-07-02", total_equity: 130 }),
      point({ trade_date: "2026-07-03", total_equity: 110 }),
    ]);
    for (const d of result) {
      expect(d.drawdown_pct).toBeLessThanOrEqual(0);
    }
  });

  it("skips null-equity points without zero-filling them", () => {
    const result = computeDrawdown([
      point({ trade_date: "2026-07-01", total_equity: 100 }),
      point({ trade_date: "2026-07-02", total_equity: null }), // skipped
      point({ trade_date: "2026-07-03", total_equity: 90 }),
    ]);
    expect(result.map((d) => d.trade_date)).toEqual([
      "2026-07-01",
      "2026-07-03",
    ]);
    expect(result.map((d) => d.drawdown_pct)).toEqual([0, -10]);
  });
});

describe("UnderwaterChart", () => {
  it("renders empty state and no svg when no data", () => {
    const { container } = render(<UnderwaterChart points={[]} />);
    expect(
      screen.getByText("배치 미가동 — equity 배치 가동 후 표시됩니다"),
    ).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders empty state when all points have null equity", () => {
    const { container } = render(
      <UnderwaterChart points={[point({ total_equity: null })]} />,
    );
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders the section title", () => {
    render(<UnderwaterChart points={[point()]} />);
    expect(
      screen.getByText("Underwater (누적 최고점 대비 낙폭)"),
    ).toBeInTheDocument();
  });
});

describe("DrawdownSvg", () => {
  it("renders an svg with at least one path at fixed dimensions", () => {
    const data = computeDrawdown([
      point({ trade_date: "2026-07-01", total_equity: 100 }),
      point({ trade_date: "2026-07-02", total_equity: 80 }),
      point({ trade_date: "2026-07-03", total_equity: 90 }),
    ]);
    const { container } = render(
      <DrawdownSvg width={400} height={256} data={data} />,
    );
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("400");
    expect(container.querySelectorAll("path").length).toBeGreaterThan(0);
  });
});
