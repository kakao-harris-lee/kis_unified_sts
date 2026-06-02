import type { BuilderState } from "@/types/builder";

export type StageId = "metadata" | "indicators" | "entry" | "exit" | "risk";
export type StageStatus = "complete" | "warning" | "empty";

/** 깔때기 피드의 스테이지 순서 (정의 → 빌딩블록 → 진입 → 청산 → 리스크). */
export const STAGE_ORDER: StageId[] = ["metadata", "indicators", "entry", "exit", "risk"];

/** 단일 스테이지의 충족 상태. 기존 page.tsx getStepStatus 규칙과 동일. */
export function computeStageStatus(state: BuilderState, id: StageId): StageStatus {
  switch (id) {
    case "metadata":
      return state.metadata.name.trim() ? "complete" : "empty";
    case "indicators":
      return state.indicators.length > 0 ? "complete" : "empty";
    case "entry":
      return state.entry.conditions.length > 0 ? "complete" : "warning";
    case "exit":
      return state.exit.conditions.length > 0 ? "complete" : "warning";
    case "risk":
      return state.risk.stopLoss.enabled ||
        state.risk.takeProfit.enabled ||
        state.risk.trailingStop.enabled
        ? "complete"
        : "empty";
  }
}

/** 전체 스테이지 status 맵. */
export function computeStageStatuses(state: BuilderState): Record<StageId, StageStatus> {
  return STAGE_ORDER.reduce(
    (acc, id) => {
      acc[id] = computeStageStatus(state, id);
      return acc;
    },
    {} as Record<StageId, StageStatus>,
  );
}

/**
 * 등록을 막는 첫 번째 미충족 스테이지(useStrategyBuilder.isValid 기준:
 * 이름 + 지표 + 진입 + 청산). 모두 충족이면 null. risk는 필수 아님.
 */
export function firstIncompleteStageId(state: BuilderState): StageId | null {
  if (!state.metadata.name.trim()) return "metadata";
  if (state.indicators.length === 0) return "indicators";
  if (state.entry.conditions.length === 0) return "entry";
  if (state.exit.conditions.length === 0) return "exit";
  return null;
}
