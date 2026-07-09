import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { OhlcvBar } from "@/lib/dashboard/marketData";
import CandleChart, { CandleSvg, toCandles, type PriceMarker } from "./CandleChart";

function bar(t: string, o: number, h: number, l: number, c: number): OhlcvBar {
  return { t, open: o, high: h, low: l, close: c, volume: 100 };
}

describe("toCandles", () => {
  it("drops bars with any null OHLC", () => {
    const bars: OhlcvBar[] = [
      bar("2026-07-01T00:00:00", 100, 110, 95, 105),
      { t: "2026-07-01T00:01:00", open: null, high: 1, low: 1, close: 1, volume: 0 },
    ];
    const candles = toCandles(bars);
    expect(candles).toHaveLength(1);
    expect(candles[0].close).toBe(105);
  });
});

describe("CandleChart", () => {
  it("renders empty state when no complete candles", () => {
    render(<CandleChart bars={[]} title="005930 진입 컨텍스트" />);
    expect(screen.getByText(/가격 데이터 없음/)).toBeInTheDocument();
  });

  it("renders the title", () => {
    render(
      <CandleChart
        bars={[bar("2026-07-01T00:00:00", 100, 110, 95, 105)]}
        title="005930 진입 컨텍스트"
      />,
    );
    expect(screen.getByText("005930 진입 컨텍스트")).toBeInTheDocument();
  });
});

describe("CandleSvg", () => {
  const candles = toCandles([
    bar("2026-07-01T00:00:00", 100, 110, 95, 105), // up (red)
    bar("2026-07-01T00:01:00", 105, 108, 98, 100), // down (blue)
    bar("2026-07-01T00:02:00", 100, 104, 99, 103),
  ]);

  it("renders a candle body rect per bar plus wick lines", () => {
    const { container } = render(
      <CandleSvg width={400} height={256} candles={candles} markers={[]} />,
    );
    expect(container.querySelector("svg")).not.toBeNull();
    // 3 body rects (at least)
    expect(container.querySelectorAll("rect").length).toBeGreaterThanOrEqual(3);
    // wick lines
    expect(container.querySelectorAll("line").length).toBeGreaterThanOrEqual(3);
  });

  it("overlays markers matching a candle timestamp", () => {
    const markers: PriceMarker[] = [
      { t: "2026-07-01T00:01:00", price: 102, side: "BUY", label: "entry" },
    ];
    const { container } = render(
      <CandleSvg width={400} height={256} candles={candles} markers={markers} />,
    );
    const polys = container.querySelectorAll("polygon");
    expect(polys.length).toBe(1);
    expect(container.textContent).toContain("BUY");
  });

  it("skips markers whose timestamp has no candle", () => {
    const markers: PriceMarker[] = [
      { t: "2099-01-01T00:00:00", price: 1, side: "SELL" },
    ];
    const { container } = render(
      <CandleSvg width={400} height={256} candles={candles} markers={markers} />,
    );
    expect(container.querySelectorAll("polygon").length).toBe(0);
  });
});
