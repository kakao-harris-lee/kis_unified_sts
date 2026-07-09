import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ExposureHistory } from "@/lib/dashboard/analytics";
import ExposureHistoryChart, {
  ExposureStackSvg,
} from "./ExposureHistoryChart";

const data: ExposureHistory = {
  status: "ok",
  symbols: ["005930", "000660"],
  points: [
    { trade_date: "2026-07-01", "005930": 700000, "000660": 500000 },
    { trade_date: "2026-07-02", "005930": 710000, "000660": 0 },
  ],
  days: 60,
};

describe("ExposureHistoryChart", () => {
  it("shows empty state when no data", () => {
    render(<ExposureHistoryChart data={undefined} />);
    expect(
      screen.getByText(/포지션 스냅샷 없음/),
    ).toBeInTheDocument();
  });

  it("renders the title when ready", () => {
    render(<ExposureHistoryChart data={data} />);
    expect(screen.getByText("심볼별 노출 추이")).toBeInTheDocument();
  });
});

describe("ExposureStackSvg", () => {
  it("renders a stacked-area path per symbol", () => {
    const { container } = render(
      <ExposureStackSvg
        width={400}
        height={256}
        points={data.points}
        symbols={data.symbols}
      />,
    );
    expect(container.querySelector("svg")).not.toBeNull();
    // one <path> per stacked symbol
    expect(container.querySelectorAll("path").length).toBeGreaterThanOrEqual(2);
  });
});
