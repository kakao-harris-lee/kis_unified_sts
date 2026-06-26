import { describe, expect, it } from "vitest";
import type { BuilderCondition, BuilderIndicator, BuilderState } from "@/types/builder";
import { toYamlStrategy, toYamlString } from "./yamlSerializer";

function indicator(
  id: string,
  indicatorId: string,
  alias: string,
  params: Record<string, number | string> = {},
  output = "value",
): BuilderIndicator {
  return {
    id,
    indicatorId,
    alias,
    params,
    output,
  };
}

function condition(
  id: string,
  leftAlias: string,
  operator: BuilderCondition["operator"],
  right: BuilderCondition["right"],
  leftOutput = "value",
): BuilderCondition {
  return {
    id,
    left: { type: "indicator", indicatorAlias: leftAlias, indicatorOutput: leftOutput },
    operator,
    right,
  };
}

function baseState(overrides: Partial<BuilderState> = {}): BuilderState {
  return {
    metadata: {
      id: "paper-rsi-v1",
      name: "Paper RSI V1",
      description: "Paper validation strategy",
      category: "oscillator",
      tags: ["paper", "rsi"],
      author: "operator",
    },
    assetClass: "stock",
    indicators: [indicator("rsi_instance", "rsi", "rsi_1", { period: "14" })],
    entry: {
      logic: "AND",
      conditions: [
        condition("entry_rsi", "rsi_1", "cross_above", { type: "value", value: 30 }),
      ],
    },
    exit: {
      logic: "AND",
      conditions: [
        condition("exit_rsi", "rsi_1", "cross_below", { type: "value", value: 70 }),
      ],
    },
    risk: {
      stopLoss: { enabled: true, percent: 5 },
      takeProfit: { enabled: false, percent: 10 },
      trailingStop: { enabled: false, percent: 3 },
    },
    ...overrides,
  };
}

describe("yamlSerializer", () => {
  it("serializes metadata, strategy, and id", () => {
    const strategy = toYamlStrategy(baseState());
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

  it("coerces numeric string params and leaves non-numeric strings unchanged", () => {
    const strategy = toYamlStrategy(baseState({
      indicators: [
        indicator("rsi_instance", "rsi", "rsi_1", {
          period: "14",
          source: "close",
          threshold: "30.5",
        }),
      ],
    }));

    expect(strategy.strategy.indicators[0].params).toEqual({
      period: 14,
      source: "close",
      threshold: 30.5,
    });
  });

  it("serializes non-default outputs and omits default value outputs from YAML text", () => {
    const strategy = toYamlStrategy(baseState({
      indicators: [
        indicator("rsi_instance", "rsi", "rsi_1", { period: "14" }, "value"),
        indicator("macd_instance", "macd", "macd_1", { fast_period: "12", slow_period: 26 }, "histogram"),
      ],
    }));
    const yaml = toYamlString(strategy);

    expect(strategy.strategy.indicators[0].output).toBeUndefined();
    expect(strategy.strategy.indicators[1].output).toBe("histogram");
    expect(yaml).toContain("      output: histogram");
    expect(yaml).not.toContain("      output: value");
  });

  it("separates candlestick indicators and serializes candlestick conditions", () => {
    const strategy = toYamlStrategy(baseState({
      indicators: [
        indicator("hammer_instance", "hammer", "hammer_1"),
      ],
      entry: {
        logic: "AND",
        conditions: [
          {
            id: "entry_hammer",
            isCandlestick: true,
            candlestickAlias: "hammer_1",
            candlestickSignal: "bullish",
            left: { type: "indicator", indicatorAlias: "hammer_1", indicatorOutput: "value" },
            operator: "greater_than",
            right: { type: "value", value: 0 },
          },
        ],
      },
      exit: {
        logic: "AND",
        conditions: [
          {
            id: "exit_hammer",
            isCandlestick: true,
            candlestickAlias: "hammer_1",
            candlestickSignal: "bearish",
            left: { type: "indicator", indicatorAlias: "hammer_1", indicatorOutput: "value" },
            operator: "greater_than",
            right: { type: "value", value: 0 },
          },
        ],
      },
    }));
    const yaml = toYamlString(strategy);

    expect(strategy.strategy.indicators).toEqual([]);
    expect(strategy.strategy.candlesticks).toEqual([{ id: "hammer", alias: "hammer_1" }]);
    expect(strategy.strategy.entry.conditions[0]).toEqual({
      candlestick: "hammer_1",
      signal: "bullish",
    });
    expect(yaml).toContain("  candlesticks:");
    expect(yaml).toContain("    - id: hammer");
    expect(yaml).toContain("      - candlestick: hammer_1");
    expect(yaml).toContain("        signal: bullish");
  });

  it("includes compare_output for indicator-to-indicator comparisons", () => {
    const strategy = toYamlStrategy(baseState({
      indicators: [
        indicator("macd_instance", "macd", "macd_1", { fast_period: 12, slow_period: 26 }),
      ],
      entry: {
        logic: "AND",
        conditions: [
          condition(
            "entry_macd_signal",
            "macd_1",
            "cross_above",
            { type: "indicator", indicatorAlias: "macd_1", indicatorOutput: "signal" },
          ),
        ],
      },
    }));
    const yaml = toYamlString(strategy);

    expect(strategy.strategy.entry.conditions[0]).toMatchObject({
      indicator: "macd_1",
      operator: "cross_above",
      compare_to: "macd_1",
      compare_output: "signal",
    });
    expect(yaml).toContain("        compare_output: signal");
  });

  it("serializes enabled risk blocks and emits an empty risk object when all are disabled", () => {
    const enabledRisk = toYamlString(toYamlStrategy(baseState({
      risk: {
        stopLoss: { enabled: true, percent: 4 },
        takeProfit: { enabled: false, percent: 10 },
        trailingStop: { enabled: true, percent: 2 },
      },
    })));
    const emptyRisk = toYamlString(toYamlStrategy(baseState({
      risk: {
        stopLoss: { enabled: false, percent: 4 },
        takeProfit: { enabled: false, percent: 10 },
        trailingStop: { enabled: false, percent: 2 },
      },
    })));

    expect(enabledRisk).toContain("risk:");
    expect(enabledRisk).toContain("  stop_loss:");
    expect(enabledRisk).toContain("    percent: 4");
    expect(enabledRisk).toContain("  trailing_stop:");
    expect(enabledRisk).toContain("    percent: 2");
    expect(enabledRisk).not.toContain("  take_profit:");
    expect(emptyRisk).toContain("risk: {}");
  });
});
