import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ColorConventionLegend from "./ColorConventionLegend";

describe("ColorConventionLegend", () => {
  it("renders the profit/loss labels", () => {
    render(<ColorConventionLegend />);
    // Labels sit as text nodes adjacent to the colored dot spans, so match
    // on substring rather than exact text-node equality.
    expect(screen.getByText(/상승\/이익/)).toBeInTheDocument();
    expect(screen.getByText(/하락\/손실/)).toBeInTheDocument();
  });

  it("exposes the KR-convention explanation via a title tooltip", () => {
    render(<ColorConventionLegend />);
    expect(
      screen.getByTitle(
        "한국 시장 관례: 빨강 = 상승/이익, 파랑 = 하락/손실 (미국 관례와 반대)",
      ),
    ).toBeInTheDocument();
  });
});
