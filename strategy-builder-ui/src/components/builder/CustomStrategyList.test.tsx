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
  getRegisteredActivity: vi.fn(async () => ({ activity: [] })),
  setRegisteredEnabled: vi.fn(),
  unregisterStrategy: vi.fn(),
}));
import { registerPaperStrategy, listRegisteredStrategies } from "@/lib/api";

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
    await userEvent.click(screen.getByRole("button", { name: /등록/ }));
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
    await userEvent.click(screen.getByRole("button", { name: /등록/ }));
    await waitFor(() => expect(registerPaperStrategy).toHaveBeenCalled());
    expect(window.alert).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText(/등록 실패/)).toBeInTheDocument());
  });
});

describe("CustomStrategyList unified lifecycle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "alert").mockImplementation(() => {});
  });

  it("로컬 드래프트가 활성 등록되면 '활성' 상태로 한 줄로 표시된다", async () => {
    vi.mocked(listRegisteredStrategies).mockResolvedValue({
      strategies: [
        { id: "s1", name: "테스트전략", asset_class: "stock", enabled: true, path: "s1.yaml" },
      ],
      total: 1,
    });
    renderList();
    // Same id → merged into one row carrying the "활성" badge (not duplicated).
    await waitFor(() => expect(screen.getByText("활성")).toBeInTheDocument());
    expect(screen.getAllByText("테스트전략")).toHaveLength(1);
  });

  it("로컬 드래프트가 없는 서버 등록 전략도 '등록됨'으로 합쳐 보여준다", async () => {
    vi.mocked(listRegisteredStrategies).mockResolvedValue({
      strategies: [
        { id: "srv-only", name: "서버전략", asset_class: "stock", enabled: false, path: "srv.yaml" },
      ],
      total: 1,
    });
    renderList();
    await waitFor(() => expect(screen.getByText("서버전략")).toBeInTheDocument());
    expect(screen.getByText("등록됨")).toBeInTheDocument();
    // The local draft is still listed alongside it.
    expect(screen.getByText("테스트전략")).toBeInTheDocument();
  });
});
