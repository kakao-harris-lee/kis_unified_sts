import { describe, it, expect } from "vitest";
import {
  mapCapabilityIndicator,
  mergeIndicatorCatalog,
  buildCatalog,
} from "@/lib/builder/indicatorCatalog";
import { ALL_INDICATORS } from "@/lib/builder/constants";
import type { CapabilityIndicator } from "@/lib/dashboard/strategyBuilder";

const rsiCap: CapabilityIndicator = {
  id: "rsi",
  name: "RSI",
  name_ko: "상대강도지수(백엔드)",
  category: "oscillator",
  description: "backend rsi",
  params: [{ name: "period", type: "number", default: 14 }],
  outputs: [{ id: "value", name: "값" }],
  default_output: "value",
  implemented: true,
  backtest_supported: true,
  runtime_supported: true,
};

describe("mapCapabilityIndicator", () => {
  it("maps snake_case fields to the frontend camelCase shape", () => {
    const def = mapCapabilityIndicator({
      id: "macd",
      name: "MACD",
      name_ko: "맥디",
      category: "oscillator",
      default_output: "signal",
    });
    expect(def.nameKo).toBe("맥디");
    expect(def.defaultOutput).toBe("signal");
    expect(def.backendUnsupported).toBe(false);
  });

  it("translates backtest_supported=false to leanUnsupported", () => {
    const def = mapCapabilityIndicator({ ...rsiCap, backtest_supported: false });
    expect(def.leanUnsupported).toBe(true);
    expect(def.runtimeUnsupported).toBe(false);
  });

  it("translates runtime_supported=false to runtimeUnsupported", () => {
    const def = mapCapabilityIndicator({ ...rsiCap, runtime_supported: false });
    expect(def.runtimeUnsupported).toBe(true);
    expect(def.leanUnsupported).toBe(false);
  });

  it("translates implemented=false and defaults implemented to true when omitted", () => {
    expect(mapCapabilityIndicator({ ...rsiCap, implemented: false }).implemented).toBe(false);
    const noFlag: CapabilityIndicator = { id: "x", name: "X", category: "misc" };
    expect(mapCapabilityIndicator(noFlag).implemented).toBe(true);
  });

  it("tolerates camelCase aliases defensively", () => {
    const def = mapCapabilityIndicator({
      id: "adx",
      name: "ADX",
      nameKo: "에이디엑스",
      category: "trend",
      defaultOutput: "value",
      backtestSupported: false,
      runtimeSupported: false,
    });
    expect(def.nameKo).toBe("에이디엑스");
    expect(def.defaultOutput).toBe("value");
    expect(def.leanUnsupported).toBe(true);
    expect(def.runtimeUnsupported).toBe(true);
  });
});

describe("mergeIndicatorCatalog — fallback (no capabilities)", () => {
  it("returns the constants seed as-is with no synthetic badges", () => {
    const merged = mergeIndicatorCatalog(null);
    expect(merged).toHaveLength(ALL_INDICATORS.length);
    expect(merged.every((d) => !d.backendUnsupported)).toBe(true);
  });

  it("treats an empty array like null (graceful)", () => {
    expect(mergeIndicatorCatalog([])).toHaveLength(ALL_INDICATORS.length);
  });
});

describe("mergeIndicatorCatalog — live (capabilities present)", () => {
  const raw: CapabilityIndicator[] = [
    rsiCap,
    {
      id: "volume_ma",
      name: "Volume MA",
      name_ko: "거래량 이동평균",
      category: "volume",
      outputs: [{ id: "value", name: "값" }],
      implemented: true,
      backtest_supported: true,
      runtime_supported: true,
    },
  ];

  it("marks constants-only ids (e.g. candlesticks) as backendUnsupported", () => {
    const merged = mergeIndicatorCatalog(raw);
    const doji = merged.find((d) => d.id === "doji");
    expect(doji?.backendUnsupported).toBe(true);
    // sma is in constants but not in the capabilities subset here.
    expect(merged.find((d) => d.id === "sma")?.backendUnsupported).toBe(true);
  });

  it("keeps capability ids supported (not backendUnsupported)", () => {
    const merged = mergeIndicatorCatalog(raw);
    expect(merged.find((d) => d.id === "rsi")?.backendUnsupported).toBe(false);
  });

  it("appends capability-only ids absent from constants", () => {
    const merged = mergeIndicatorCatalog(raw);
    const volumeMa = merged.find((d) => d.id === "volume_ma");
    expect(volumeMa).toBeDefined();
    expect(volumeMa?.backendUnsupported).toBe(false);
    // constants has no volume_ma, so it must come from capabilities.
    expect(ALL_INDICATORS.some((d) => d.id === "volume_ma")).toBe(false);
  });

  it("preserves constants UI meta (futuresApplicability) on merged capability items", () => {
    const vwapCap: CapabilityIndicator = {
      id: "vwap",
      name: "VWAP",
      name_ko: "VWAP",
      category: "volume",
      outputs: [{ id: "value", name: "값" }],
    };
    const merged = mergeIndicatorCatalog([vwapCap]);
    const vwap = merged.find((d) => d.id === "vwap");
    // constants marks vwap as futures-degraded; capabilities does not carry it.
    expect(vwap?.futuresApplicability).toBe("degraded");
  });

  it("keeps the total count = constants ∪ capability-only", () => {
    const merged = mergeIndicatorCatalog(raw);
    // volume_ma is the only capability-only id here.
    expect(merged).toHaveLength(ALL_INDICATORS.length + 1);
  });
});

describe("buildCatalog helpers", () => {
  it("exposes getById / byCategory / search over the merged list", () => {
    const catalog = buildCatalog([rsiCap], "live");
    expect(catalog.status).toBe("live");
    expect(catalog.getById("rsi")?.nameKo).toBeDefined();
    expect(catalog.byCategory("candlestick").length).toBeGreaterThan(0);
    expect(catalog.search("rsi").some((d) => d.id === "rsi")).toBe(true);
    expect(catalog.search("")).toEqual([]);
  });
});
