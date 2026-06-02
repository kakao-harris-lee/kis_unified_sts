import { describe, it, expect } from "vitest";
import { INITIAL_STATE } from "@/hooks/useStrategyBuilder";
import type { BuilderState } from "@/types/builder";
import {
  computeStageStatus,
  computeStageStatuses,
  firstIncompleteStageId,
  STAGE_ORDER,
} from "./stageStatus";

function withName(state: BuilderState, name: string): BuilderState {
  return { ...state, metadata: { ...state.metadata, name } };
}

describe("computeStageStatus", () => {
  it("metadata: 이름 없으면 empty, 있으면 complete", () => {
    expect(computeStageStatus(withName(INITIAL_STATE, ""), "metadata")).toBe("empty");
    expect(computeStageStatus(withName(INITIAL_STATE, "내전략"), "metadata")).toBe("complete");
  });

  it("기본 상태는 이름이 비어 metadata가 empty (placeholder 이름 금지)", () => {
    // INITIAL_STATE must NOT ship a placeholder name like "custom_strategy",
    // else a fresh form looks 완료 and can register an unnamed strategy.
    expect(INITIAL_STATE.metadata.name).toBe("");
    expect(computeStageStatus(INITIAL_STATE, "metadata")).toBe("empty");
  });

  it("indicators: 비어있으면 empty", () => {
    expect(computeStageStatus(INITIAL_STATE, "indicators")).toBe("empty");
  });

  it("entry/exit: 조건 없으면 warning", () => {
    expect(computeStageStatus(INITIAL_STATE, "entry")).toBe("warning");
    expect(computeStageStatus(INITIAL_STATE, "exit")).toBe("warning");
  });

  it("risk: 모든 토글 off면 empty", () => {
    expect(computeStageStatus(INITIAL_STATE, "risk")).toBe("empty");
  });
});

describe("STAGE_ORDER", () => {
  it("정보→지표→진입→청산→리스크 순서", () => {
    expect(STAGE_ORDER).toEqual(["metadata", "indicators", "entry", "exit", "risk"]);
  });
});

describe("computeStageStatuses", () => {
  it("모든 스테이지 키를 반환", () => {
    const all = computeStageStatuses(INITIAL_STATE);
    expect(Object.keys(all).sort()).toEqual([...STAGE_ORDER].sort());
  });
});

describe("firstIncompleteStageId", () => {
  it("이름이 비면 metadata가 첫 미충족", () => {
    expect(firstIncompleteStageId(withName(INITIAL_STATE, ""))).toBe("metadata");
  });
  it("이름만 있으면 indicators가 첫 미충족", () => {
    expect(firstIncompleteStageId(withName(INITIAL_STATE, "내전략"))).toBe("indicators");
  });
});
