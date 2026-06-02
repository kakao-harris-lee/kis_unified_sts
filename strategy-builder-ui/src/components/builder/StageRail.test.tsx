import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StageRail, type StageRailItem } from "./StageRail";

const STAGES: StageRailItem[] = [
  { id: "metadata", stepNum: 1, shortLabel: "정보", status: "complete" },
  { id: "indicators", stepNum: 2, shortLabel: "지표", status: "empty" },
  { id: "entry", stepNum: 3, shortLabel: "진입", status: "warning" },
];

describe("StageRail", () => {
  it("모든 스테이지 라벨을 렌더한다", () => {
    render(<StageRail stages={STAGES} activeId="metadata" onJump={() => {}} />);
    expect(screen.getByText("정보")).toBeInTheDocument();
    expect(screen.getByText("지표")).toBeInTheDocument();
    expect(screen.getByText("진입")).toBeInTheDocument();
  });

  it("chip 클릭 시 onJump(id)를 호출한다", async () => {
    const onJump = vi.fn();
    render(<StageRail stages={STAGES} activeId="metadata" onJump={onJump} />);
    await userEvent.click(screen.getByText("진입"));
    expect(onJump).toHaveBeenCalledWith("entry");
  });

  it("active 스테이지에 aria-current=step를 설정한다", () => {
    render(<StageRail stages={STAGES} activeId="indicators" onJump={() => {}} />);
    const active = screen.getByText("지표").closest("button");
    expect(active).toHaveAttribute("aria-current", "step");
  });
});
