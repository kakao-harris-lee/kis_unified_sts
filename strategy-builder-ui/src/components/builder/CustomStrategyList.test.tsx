import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "@/components/ui";
import { INITIAL_STATE } from "@/hooks/useStrategyBuilder";
import type { StoredStrategy } from "@/types/builder";
import { CustomStrategyList } from "./CustomStrategyList";

vi.mock("@/lib/api", () => ({
  registerPaperStrategy: vi.fn(),
  listRegisteredStrategies: vi.fn(async () => ({ strategies: [], total: 0 })),
}));
import { registerPaperStrategy } from "@/lib/api";

const strategy: StoredStrategy = {
  id: "s1",
  name: "테스트전략",
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
  state: INITIAL_STATE,
};

function renderList() {
  return render(
    <ToastProvider>
      <CustomStrategyList
        strategies={[strategy]}
        selectedId={null}
        onSelect={() => {}}
        onDelete={() => {}}
        onDuplicate={() => {}}
        onCreateNew={() => {}}
      />
    </ToastProvider>,
  );
}

describe("CustomStrategyList register feedback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "alert").mockImplementation(() => {});
  });

  it("등록 성공 시 alert 대신 toast를 띄운다", async () => {
    vi.mocked(registerPaperStrategy).mockResolvedValueOnce({
      id: "s1", name: "테스트전략", asset_class: "stock", enabled: false, path: "x.yaml",
    });
    renderList();
    await userEvent.click(screen.getByRole("button", { name: "전략 메뉴" }));
    await userEvent.click(screen.getByRole("button", { name: /페이퍼로 등록/ }));
    await waitFor(() => expect(registerPaperStrategy).toHaveBeenCalled());
    expect(window.alert).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByText(/등록되었습니다|등록했습니다/)).toBeInTheDocument(),
    );
  });

  it("등록 실패 시 error toast를 띄운다", async () => {
    vi.mocked(registerPaperStrategy).mockRejectedValueOnce(new Error("boom"));
    renderList();
    await userEvent.click(screen.getByRole("button", { name: "전략 메뉴" }));
    await userEvent.click(screen.getByRole("button", { name: /페이퍼로 등록/ }));
    await waitFor(() => expect(registerPaperStrategy).toHaveBeenCalled());
    expect(window.alert).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText(/등록 실패/)).toBeInTheDocument());
  });
});
