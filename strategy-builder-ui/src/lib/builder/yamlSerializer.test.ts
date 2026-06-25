import { describe, expect, it } from "vitest";
import type { BuilderState } from "@/types/builder";
import { toYamlStrategy, toYamlString } from "./yamlSerializer";

const baseState: BuilderState = {
  metadata: {
    id: "paper-rsi-v1",
    name: "Paper RSI V1",
    description: "Paper validation strategy",
    category: "oscillator",
    tags: ["paper", "rsi"],
    author: "operator",
  },
  assetClass: "stock",
  indicators: [
    {
      id: "rsi_instance",
      indicatorId: "rsi",
      alias: "rsi_1",
      params: { period: "14" },
      output: "value",
    },
  ],
  entry: {
    logic: "AND",
    conditions: [
      {
        id: "entry_rsi",
        left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
        operator: "cross_above",
        right: { type: "value", value: 30 },
      },
    ],
  },
  exit: {
    logic: "AND",
    conditions: [
      {
        id: "exit_rsi",
        left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
        operator: "cross_below",
        right: { type: "value", value: 70 },
      },
    ],
  },
  risk: {
    stopLoss: { enabled: true, percent: 5 },
    takeProfit: { enabled: false, percent: 10 },
    trailingStop: { enabled: false, percent: 3 },
  },
};

describe("yamlSerializer", () => {
  it("serializes metadata, strategy, and id", () => {
    const strategy = toYamlStrategy(baseState);
    const yaml = toYamlString(strategy);

    expect(strategy.metadata).toEqual({
      name: "Paper RSI V1",
      description: "Paper validation strategy",
      author: "operator",
      tags: ["paper", "rsi"],
    });
    expect(strategy.strategy.id).toBe("paper-rsi-v1");
    expect(yaml).toContain("metadata:");
    expect(yaml).toContain('  name: "Paper RSI V1"');
    expect(yaml).toContain("strategy:");
    expect(yaml).toContain("  id: paper-rsi-v1");
  });
});
