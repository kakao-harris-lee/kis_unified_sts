import { describe, expect, it } from "vitest";
import type { BuilderCondition, BuilderIndicator, BuilderState } from "@/types/builder";
import { builderReducer, INITIAL_STATE } from "./reducer";

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

function valueCondition(
  id: string,
  alias: string,
  value: number,
): BuilderCondition {
  return {
    id,
    left: { type: "indicator", indicatorAlias: alias, indicatorOutput: "value" },
    operator: "greater_than",
    right: { type: "value", value },
  };
}

describe("builderReducer", () => {
  it("updates metadata without mutating INITIAL_STATE", () => {
    const next = builderReducer(INITIAL_STATE, {
      type: "SET_METADATA",
      payload: {
        id: "mean-reversion-v1",
        name: "Mean Reversion V1",
        tags: ["paper", "stock"],
      },
    });

    expect(next.metadata).toMatchObject({
      id: "mean-reversion-v1",
      name: "Mean Reversion V1",
      tags: ["paper", "stock"],
    });
    expect(next).not.toBe(INITIAL_STATE);
    expect(next.metadata).not.toBe(INITIAL_STATE.metadata);
    expect(INITIAL_STATE.metadata).toEqual({
      id: "",
      name: "",
      description: "",
      category: "custom",
      tags: [],
      author: "user",
    });
  });

  it("regenerates auto conditions for an oscillator and same-type moving averages", () => {
    const rsi = indicator("rsi-instance", "rsi", "rsi_1", { period: 14 });
    const smaFast = indicator("sma-fast", "sma", "sma_fast", { period: 5 });
    const smaSlow = indicator("sma-slow", "sma", "sma_slow", { period: 20 });

    const withRsi = builderReducer(INITIAL_STATE, {
      type: "ADD_INDICATOR_WITH_AUTO",
      payload: rsi,
    });

    expect(withRsi.entry.conditions).toHaveLength(1);
    expect(withRsi.entry.conditions[0]).toMatchObject({
      left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
      operator: "cross_above",
      right: { type: "value", value: 30 },
    });
    expect(withRsi.exit.conditions[0]).toMatchObject({
      left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
      operator: "cross_below",
      right: { type: "value", value: 70 },
    });

    const withOneMa = builderReducer(withRsi, {
      type: "ADD_INDICATOR_WITH_AUTO",
      payload: smaFast,
    });
    expect(withOneMa.entry.conditions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          left: { type: "price", priceField: "close" },
          operator: "cross_above",
          right: { type: "indicator", indicatorAlias: "sma_fast", indicatorOutput: "value" },
        }),
      ])
    );

    const withTwoMas = builderReducer(withOneMa, {
      type: "ADD_INDICATOR_WITH_AUTO",
      payload: smaSlow,
    });

    expect(withTwoMas.indicators.map((ind) => ind.alias)).toEqual(["rsi_1", "sma_fast", "sma_slow"]);
    expect(withTwoMas.entry.conditions).toHaveLength(2);
    expect(withTwoMas.exit.conditions).toHaveLength(2);
    expect(withTwoMas.entry.conditions.every((condition) => condition.id.startsWith("auto_"))).toBe(true);
    expect(withTwoMas.entry.conditions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          left: { type: "indicator", indicatorAlias: "sma_fast", indicatorOutput: "value" },
          operator: "cross_above",
          right: { type: "indicator", indicatorAlias: "sma_slow", indicatorOutput: "value" },
        }),
        expect.objectContaining({
          left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
          operator: "cross_above",
          right: { type: "value", value: 30 },
        }),
      ])
    );
    expect(withTwoMas.exit.conditions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          left: { type: "indicator", indicatorAlias: "sma_fast", indicatorOutput: "value" },
          operator: "cross_below",
          right: { type: "indicator", indicatorAlias: "sma_slow", indicatorOutput: "value" },
        }),
        expect.objectContaining({
          left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
          operator: "cross_below",
          right: { type: "value", value: 70 },
        }),
      ])
    );
    expect(
      withTwoMas.entry.conditions.some(
        (condition) => condition.left.type === "price" && condition.right.indicatorAlias === "sma_fast"
      )
    ).toBe(false);
  });

  it("removes manual conditions that reference a removed indicator alias", () => {
    const rsi = indicator("rsi-instance", "rsi", "rsi_1");
    const sma = indicator("sma-instance", "sma", "sma_1");
    const keepEntry: BuilderCondition = {
      id: "keep-entry",
      left: { type: "price", priceField: "close" },
      operator: "greater_than",
      right: { type: "value", value: 100 },
    };
    const keepExit: BuilderCondition = {
      id: "keep-exit",
      left: { type: "indicator", indicatorAlias: "sma_1", indicatorOutput: "value" },
      operator: "less_than",
      right: { type: "value", value: 95 },
    };
    const state: BuilderState = {
      ...INITIAL_STATE,
      indicators: [rsi, sma],
      entry: {
        logic: "AND",
        conditions: [
          valueCondition("remove-left-ref", "rsi_1", 30),
          keepEntry,
        ],
      },
      exit: {
        logic: "AND",
        conditions: [
          {
            id: "remove-right-ref",
            left: { type: "indicator", indicatorAlias: "sma_1", indicatorOutput: "value" },
            operator: "cross_above",
            right: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
          },
          {
            id: "remove-candlestick-ref",
            isCandlestick: true,
            candlestickAlias: "rsi_1",
            candlestickSignal: "bearish",
            left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
            operator: "greater_than",
            right: { type: "value", value: 0 },
          },
          keepExit,
        ],
      },
    };

    const next = builderReducer(state, {
      type: "REMOVE_INDICATOR",
      payload: "rsi-instance",
    });

    expect(next.indicators.map((ind) => ind.alias)).toEqual(["sma_1"]);
    expect(next.entry.conditions.map((condition) => condition.id)).toEqual(["keep-entry"]);
    expect(next.exit.conditions.map((condition) => condition.id)).toEqual(["keep-exit"]);
  });

  it("repairs duplicate indicator IDs and defaults missing assetClass on LOAD_STATE", () => {
    const loaded = {
      ...INITIAL_STATE,
      assetClass: undefined,
      indicators: [
        indicator("duplicate-id", "rsi", "rsi_1"),
        indicator("duplicate-id", "sma", "sma_1"),
      ],
    } as unknown as BuilderState;

    const next = builderReducer(INITIAL_STATE, {
      type: "LOAD_STATE",
      payload: loaded,
    });

    expect(next.assetClass).toBe("stock");
    expect(next.indicators).toHaveLength(2);
    expect(next.indicators[0].id).toBe("duplicate-id");
    expect(next.indicators[1].id).not.toBe("duplicate-id");
    expect(next.indicators[1].id).toMatch(/^sma_/);
    expect(new Set(next.indicators.map((ind) => ind.id)).size).toBe(2);
  });

  it("resets to INITIAL_STATE without preserving mutated previous state", () => {
    const previous: BuilderState = {
      ...INITIAL_STATE,
      metadata: {
        ...INITIAL_STATE.metadata,
        name: "Temporary Draft",
      },
      indicators: [indicator("rsi-instance", "rsi", "rsi_1")],
      entry: {
        logic: "AND",
        conditions: [valueCondition("entry-rsi", "rsi_1", 30)],
      },
    };

    const next = builderReducer(previous, { type: "RESET" });

    expect(next).toBe(INITIAL_STATE);
    expect(next).not.toBe(previous);
    expect(next.metadata.name).toBe("");
    expect(next.indicators).toEqual([]);
    expect(next.entry.conditions).toEqual([]);
  });
});
