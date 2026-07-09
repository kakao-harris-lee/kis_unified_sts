import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StrategyCorrelation } from "@/lib/dashboard/analytics";
import CorrelationHeatmap, { CorrelationGrid } from "./CorrelationHeatmap";

const data: StrategyCorrelation = {
  status: "ok",
  strategies: ["a", "b"],
  matrix: [
    [1.0, 0.8],
    [0.8, 1.0],
  ],
  days: 90,
};

describe("CorrelationHeatmap", () => {
  it("shows insufficient-data empty state", () => {
    render(
      <CorrelationHeatmap
        data={{ status: "insufficient_data", strategies: [], matrix: [], days: 90 }}
      />,
    );
    expect(screen.getByText(/전략 2개 이상/)).toBeInTheDocument();
  });

  it("shows empty state when no data", () => {
    render(<CorrelationHeatmap data={undefined} />);
    expect(screen.getByText(/거래 데이터 없음/)).toBeInTheDocument();
  });

  it("renders the title when data is ready", () => {
    render(<CorrelationHeatmap data={data} />);
    expect(screen.getByText("전략 상관 (일 PnL)")).toBeInTheDocument();
  });
});

describe("CorrelationGrid", () => {
  it("renders one rect per matrix cell plus axis labels", () => {
    const { container } = render(
      <CorrelationGrid width={300} height={300} data={data} />,
    );
    // 2x2 = 4 cells
    expect(container.querySelectorAll("rect").length).toBe(4);
    // strategy labels present (row + column → duplicated text ok)
    expect(container.textContent).toContain("a");
    expect(container.textContent).toContain("b");
  });
});
