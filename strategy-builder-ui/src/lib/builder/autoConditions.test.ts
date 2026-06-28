import { describe, expect, it } from "vitest";
import type { BuilderIndicator } from "@/types/builder";
import { generateAutoConditions } from "./autoConditions";

function indicator(
  id: string,
  indicatorId: string,
  alias: string,
  params: Record<string, number | string> = {}
): BuilderIndicator {
  return {
    id,
    indicatorId,
    alias,
    params,
    output: "value",
  };
}

describe("generateAutoConditions", () => {
  it("creates default RSI entry and exit thresholds", () => {
    const result = generateAutoConditions([
      indicator("rsi-instance", "rsi", "rsi_1", { period: 14 }),
    ]);

    expect(result.entry[0]).toMatchObject({
      left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
      operator: "cross_above",
      right: { type: "value", value: 30 },
    });
    expect(result.exit[0]).toMatchObject({
      left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
      operator: "cross_below",
      right: { type: "value", value: 70 },
    });
  });

  it("creates same-type moving-average crossover conditions", () => {
    const result = generateAutoConditions([
      indicator("sma-fast", "sma", "sma_fast", { period: 5 }),
      indicator("sma-slow", "sma", "sma_slow", { period: 20 }),
    ]);

    expect(result.entry).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          left: { type: "indicator", indicatorAlias: "sma_fast", indicatorOutput: "value" },
          operator: "cross_above",
          right: { type: "indicator", indicatorAlias: "sma_slow", indicatorOutput: "value" },
        }),
      ])
    );
    expect(result.exit).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          left: { type: "indicator", indicatorAlias: "sma_fast", indicatorOutput: "value" },
          operator: "cross_below",
          right: { type: "indicator", indicatorAlias: "sma_slow", indicatorOutput: "value" },
        }),
      ])
    );
  });
});
