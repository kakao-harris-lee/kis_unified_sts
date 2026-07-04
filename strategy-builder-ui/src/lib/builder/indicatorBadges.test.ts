import { describe, it, expect } from "vitest";
import { resolveIndicatorBadges, primaryBadge } from "@/lib/builder/indicatorBadges";

describe("resolveIndicatorBadges", () => {
  it("returns no badges for a fully supported indicator", () => {
    const state = resolveIndicatorBadges({}, "stock");
    expect(state.disabled).toBe(false);
    expect(state.locked).toBe(false);
    expect(state.badges).toEqual([]);
    expect(primaryBadge(state)).toBeNull();
  });

  it("locks + disables when implemented === false (지원 예정)", () => {
    const state = resolveIndicatorBadges({ implemented: false }, "stock");
    expect(state.disabled).toBe(true);
    expect(state.locked).toBe(true);
    expect(state.badges[0].kind).toBe("unimplemented");
    expect(state.badges[0].label).toBe("지원 예정");
  });

  it("unimplemented takes precedence over every other flag", () => {
    const state = resolveIndicatorBadges(
      { implemented: false, leanUnsupported: true, backendUnsupported: true },
      "stock",
    );
    expect(state.badges).toHaveLength(1);
    expect(state.badges[0].kind).toBe("unimplemented");
  });

  it("fires the dormant leanUnsupported branch (백테스트 미지원, not disabled)", () => {
    const state = resolveIndicatorBadges({ leanUnsupported: true }, "stock");
    expect(state.disabled).toBe(false);
    expect(primaryBadge(state)?.kind).toBe("backtest_unsupported");
    expect(primaryBadge(state)?.label).toBe("백테스트 미지원");
  });

  it("emits the new runtime badge (런타임 미지원)", () => {
    const state = resolveIndicatorBadges({ runtimeUnsupported: true }, "stock");
    expect(primaryBadge(state)?.kind).toBe("runtime_unsupported");
    expect(primaryBadge(state)?.label).toBe("런타임 미지원");
  });

  it("marks backend-missing ids as selectable-but-warned (백엔드 미지원)", () => {
    const state = resolveIndicatorBadges({ backendUnsupported: true }, "stock");
    expect(state.disabled).toBe(false); // 선택 가능
    expect(primaryBadge(state)?.kind).toBe("backend_unsupported");
    expect(primaryBadge(state)?.label).toBe("백엔드 미지원");
  });

  it("shows futures degradation only in futures mode", () => {
    const stock = resolveIndicatorBadges({ futuresApplicability: "degraded" }, "stock");
    expect(stock.badges).toEqual([]);
    const futures = resolveIndicatorBadges({ futuresApplicability: "degraded" }, "futures");
    expect(primaryBadge(futures)?.kind).toBe("futures_degraded");
  });

  it("stacks multiple non-blocking badges in precedence order", () => {
    const state = resolveIndicatorBadges(
      {
        backendUnsupported: true,
        leanUnsupported: true,
        runtimeUnsupported: true,
        futuresApplicability: "degraded",
      },
      "futures",
    );
    expect(state.badges.map((b) => b.kind)).toEqual([
      "backend_unsupported",
      "backtest_unsupported",
      "runtime_unsupported",
      "futures_degraded",
    ]);
  });
});
