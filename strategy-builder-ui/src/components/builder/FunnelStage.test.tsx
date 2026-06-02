import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FunnelStage } from "./FunnelStage";

describe("FunnelStage", () => {
  it("번호·제목·children을 렌더한다", () => {
    render(
      <FunnelStage id="entry" stepNum={3} title="진입 조건" status="warning">
        <div>자식내용</div>
      </FunnelStage>,
    );
    expect(screen.getByText("진입 조건")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("자식내용")).toBeInTheDocument();
  });

  it("status별 chip을 렌더한다", () => {
    const { rerender } = render(
      <FunnelStage id="a" stepNum={1} title="A" status="complete">x</FunnelStage>,
    );
    expect(screen.getByTestId("stage-status-complete")).toBeInTheDocument();
    rerender(<FunnelStage id="a" stepNum={1} title="A" status="warning">x</FunnelStage>);
    expect(screen.getByTestId("stage-status-warning")).toBeInTheDocument();
    rerender(<FunnelStage id="a" stepNum={1} title="A" status="empty">x</FunnelStage>);
    expect(screen.getByTestId("stage-status-empty")).toBeInTheDocument();
  });

  it("anchor id를 stage-<id>로 설정한다", () => {
    const { container } = render(
      <FunnelStage id="risk" stepNum={5} title="리스크" status="empty">x</FunnelStage>,
    );
    expect(container.querySelector("#stage-risk")).not.toBeNull();
  });

  it("기본적으로 connector를 표시한다", () => {
    const { container } = render(
      <FunnelStage id="x" stepNum={1} title="T" status="empty">x</FunnelStage>,
    );
    expect(container.querySelector(".bg-gradient-to-b")).not.toBeNull();
  });

  it("showConnector=false 일 때 connector를 숨긴다", () => {
    const { container } = render(
      <FunnelStage id="x" stepNum={1} title="T" status="empty" showConnector={false}>x</FunnelStage>,
    );
    expect(container.querySelector(".bg-gradient-to-b")).toBeNull();
  });
});
