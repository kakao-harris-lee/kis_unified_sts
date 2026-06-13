import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BuilderActionBar } from "./BuilderActionBar";

const baseProps = {
  isValid: true,
  validationErrors: [] as string[],
  registering: false,
  lastRegistered: null,
  onSave: () => {},
  onRegister: () => {},
  onDismissGuidance: () => {},
};

describe("BuilderActionBar", () => {
  it("유효하지 않으면 저장/등록 버튼이 비활성", () => {
    render(
      <BuilderActionBar
        {...baseProps}
        isValid={false}
        validationErrors={["전략 이름을 입력하세요"]}
      />,
    );
    expect(screen.getByRole("button", { name: /저장/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /등록/ })).toBeDisabled();
  });

  it("유효하면 onSave/onRegister를 호출한다", async () => {
    const onSave = vi.fn();
    const onRegister = vi.fn();
    render(<BuilderActionBar {...baseProps} onSave={onSave} onRegister={onRegister} />);
    await userEvent.click(screen.getByRole("button", { name: /저장/ }));
    await userEvent.click(screen.getByRole("button", { name: /등록/ }));
    expect(onSave).toHaveBeenCalledOnce();
    expect(onRegister).toHaveBeenCalledOnce();
  });

  it("등록 중에는 등록 버튼이 비활성", () => {
    render(<BuilderActionBar {...baseProps} registering={true} />);
    const btn = screen.getByRole("button", { name: /등록/ });
    expect(btn).toBeDisabled();
    expect(btn.querySelector(".animate-spin")).not.toBeNull();
  });

  it("lastRegistered가 있으면 안내 카드를 노출하고 닫기로 dismiss", async () => {
    const onDismissGuidance = vi.fn();
    render(
      <BuilderActionBar
        {...baseProps}
        lastRegistered={{ name: "내전략" }}
        onDismissGuidance={onDismissGuidance}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("내전략");
    expect(screen.getByRole("status")).toHaveTextContent("비활성");
    await userEvent.click(screen.getByRole("button", { name: "안내 닫기" }));
    expect(onDismissGuidance).toHaveBeenCalledOnce();
  });
});
