/**
 * Indicator badge resolution — pure logic shared by the picker's three render
 * spots (selected header / search results / category list) plus the popular
 * grid. Centralises precedence + the disabled/locked decision so the dormant
 * `implemented === false` and `leanUnsupported` branches actually fire once the
 * catalog is capability-driven, and the two new badges (런타임/백엔드 미지원) are
 * consistent everywhere.
 */

import type { IndicatorDefinition } from "@/types/builder";

export type IndicatorBadgeKind =
  | "unimplemented"
  | "backend_unsupported"
  | "backtest_unsupported"
  | "runtime_unsupported"
  | "futures_degraded";

export interface IndicatorBadge {
  kind: IndicatorBadgeKind;
  /** Short label rendered in the badge chip. */
  label: string;
  /** Tooltip / title text. */
  title: string;
}

export interface IndicatorBadgeState {
  /** Block the "add" action (only `implemented === false`). */
  disabled: boolean;
  /** Render the Lock icon instead of the amber warning icon. */
  locked: boolean;
  /** Ordered by precedence; a compact spot renders `badges[0]`, the selected
   * header renders all. */
  badges: IndicatorBadge[];
}

type BadgeInput = Pick<
  IndicatorDefinition,
  | "implemented"
  | "leanUnsupported"
  | "runtimeUnsupported"
  | "backendUnsupported"
  | "futuresApplicability"
>;

export function resolveIndicatorBadges(
  def: BadgeInput,
  assetClass: "stock" | "futures",
): IndicatorBadgeState {
  // Hard block: not implemented on the backend yet.
  if (def.implemented === false) {
    return {
      disabled: true,
      locked: true,
      badges: [
        {
          kind: "unimplemented",
          label: "지원 예정",
          title: "아직 구현되지 않은 지표입니다 (추가 불가)",
        },
      ],
    };
  }

  const badges: IndicatorBadge[] = [];

  if (def.backendUnsupported) {
    badges.push({
      kind: "backend_unsupported",
      label: "백엔드 미지원",
      title:
        "백엔드 capabilities에 없는 지표입니다 — 선택은 가능하나 백테스트/실행이 보장되지 않습니다",
    });
  }
  if (def.leanUnsupported) {
    badges.push({
      kind: "backtest_unsupported",
      label: "백테스트 미지원",
      title: "Lean 백테스트 미지원 (p1 자체 실행만 가능)",
    });
  }
  if (def.runtimeUnsupported) {
    badges.push({
      kind: "runtime_unsupported",
      label: "런타임 미지원",
      title: "실시간 런타임에서 지원되지 않는 지표입니다",
    });
  }
  if (assetClass === "futures" && def.futuresApplicability === "degraded") {
    badges.push({
      kind: "futures_degraded",
      label: "선물 권장 안 함",
      title: "코스피200 미니의 낮은 유동성에서 신뢰도 저하 — 선물 권장 안 함",
    });
  }

  return { disabled: false, locked: false, badges };
}

/** Highest-precedence badge for compact single-badge render spots. */
export function primaryBadge(state: IndicatorBadgeState): IndicatorBadge | null {
  return state.badges[0] ?? null;
}
