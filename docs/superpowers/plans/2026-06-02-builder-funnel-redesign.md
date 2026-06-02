# 전략 빌더 흐름 세로 깔때기 재구성 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/builder` 페이지의 5단계 가로 스텝퍼를 세로 깔때기(funnel) 피드 + 스티키 액션바로 재구성하고, 페이퍼 등록을 `alert()` 대신 toast + 다음단계 안내로 개선한다 (프론트엔드 전용).

**Architecture:** 순수 status 헬퍼(`stageStatus.ts`) 위에 3개 presentational 컴포넌트(`FunnelStage`/`StageRail`/`BuilderActionBar`)를 쌓고, `page.tsx`에서 기존 hook/섹션 컴포넌트와 배선한다. 등록 API 호출·toast는 page.tsx 핸들러가 담당하고, 시각적 개선(상태 chip·안내 카드)은 테스트 가능한 presentational 컴포넌트에 둔다. 백엔드/API/런타임 변경 없음.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Tailwind, lucide-react. 테스트는 신규 도입하는 vitest + React Testing Library + jsdom.

**Spec:** `docs/superpowers/specs/2026-06-02-builder-funnel-redesign-design.md`

**작업 디렉토리:** 모든 경로는 `strategy-builder-ui/` 기준 (예: `src/...`). 명령은 `cd strategy-builder-ui` 후 실행.

---

## File Structure

| 파일 | 책임 | 상태 |
|------|------|------|
| `vitest.config.ts` | vitest 설정(jsdom, `@` alias, setup) | 생성 |
| `src/test/setup.ts` | jest-dom 매처 + afterEach cleanup | 생성 |
| `src/lib/builder/stageStatus.ts` | 스테이지 status 순수 계산 + 첫 미충족 스테이지 | 생성 |
| `src/components/builder/FunnelStage.tsx` | 스테이지 래퍼 카드(번호·제목·status chip·커넥터) | 생성 |
| `src/components/builder/StageRail.tsx` | 좌측 세로 미니레일(점프 네비) | 생성 |
| `src/components/builder/BuilderActionBar.tsx` | 하단 스티키 액션바(저장/등록 + 안내 카드) | 생성 |
| `src/components/builder/index.ts` | 신규 컴포넌트 export | 수정 |
| `src/components/builder/CustomStrategyList.tsx` | 등록 피드백 `alert()` → toast | 수정 |
| `src/app/builder/page.tsx` | 스텝퍼 → 깔때기 피드 재구성, draft 직접 등록 배선 | 수정 |
| `package.json` | `test` / `test:watch` 스크립트 + devDeps | 수정 |

---

## Task 0: 테스트 인프라 스캐폴딩 (vitest + RTL)

**Files:**
- Modify: `package.json`
- Create: `vitest.config.ts`
- Create: `src/test/setup.ts`
- Create: `src/lib/builder/__smoke__.test.ts` (스모크, 마지막에 삭제)

- [ ] **Step 1: 테스트 devDeps 설치**

Run (in `strategy-builder-ui/`):
```bash
npm i -D vitest@^3 @vitejs/plugin-react@^4 jsdom@^26 @testing-library/react@^16 @testing-library/jest-dom@^6 @testing-library/user-event@^14
```
Expected: 설치 성공. (React 19 호환을 위해 `@testing-library/react`는 반드시 v16+.)

- [ ] **Step 2: `vitest.config.ts` 생성**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": resolve(__dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
```

- [ ] **Step 3: `src/test/setup.ts` 생성**

`src/` 하위에 두어 tsconfig(`**/*.ts`)가 jest-dom 타입 augmentation을 로드하도록 한다.
```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 4: `package.json`에 test 스크립트 추가**

`scripts`에 추가 (기존 dev/build/start/lint 유지):
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 5: 스모크 테스트 작성**

Create `src/lib/builder/__smoke__.test.ts`:
```ts
import { describe, it, expect } from "vitest";

describe("test infra", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 6: 스모크 테스트 실행**

Run: `npm test`
Expected: PASS (1 passed). vitest + jsdom이 동작함을 확인.

- [ ] **Step 7: 타입체크가 깨지지 않는지 확인**

Run: `npx tsc --noEmit`
Expected: 에러 없음. (만약 `next build`/`tsc`가 test 파일 때문에 깨지면 tsconfig `exclude`에 `"**/*.test.ts"`, `"**/*.test.tsx"`, `"vitest.config.ts"`를 추가하고 vitest 타이핑에 의존 — 단 가능하면 include 유지.)

- [ ] **Step 8: 스모크 파일 삭제 후 커밋**

```bash
rm src/lib/builder/__smoke__.test.ts
git add package.json package-lock.json vitest.config.ts src/test/setup.ts
git commit -m "test(builder-ui): scaffold vitest + react-testing-library"
```

---

## Task 1: `stageStatus.ts` 순수 헬퍼 (TDD)

현 `page.tsx`의 인라인 `getStepStatus` 규칙을 순수 함수로 추출 — `FunnelStage`/`StageRail`/`page`가 공유.

**Files:**
- Create: `src/lib/builder/stageStatus.ts`
- Test: `src/lib/builder/stageStatus.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

`src/lib/builder/stageStatus.test.ts`:
```ts
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
  it("초기 상태는 metadata가 첫 미충족", () => {
    expect(firstIncompleteStageId(INITIAL_STATE)).toBe("metadata");
  });
  it("이름만 있으면 indicators가 첫 미충족", () => {
    expect(firstIncompleteStageId(withName(INITIAL_STATE, "내전략"))).toBe("indicators");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npm test -- stageStatus`
Expected: FAIL ("Failed to resolve import ./stageStatus" 또는 함수 미정의).

- [ ] **Step 3: `stageStatus.ts` 구현**

```ts
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
```

- [ ] **Step 4: 통과 확인**

Run: `npm test -- stageStatus`
Expected: PASS (all tests).

- [ ] **Step 5: 커밋**

```bash
git add src/lib/builder/stageStatus.ts src/lib/builder/stageStatus.test.ts
git commit -m "feat(builder-ui): add stageStatus pure helper"
```

---

## Task 2: `FunnelStage` 컴포넌트 (TDD)

**Files:**
- Create: `src/components/builder/FunnelStage.tsx`
- Test: `src/components/builder/FunnelStage.test.tsx`

- [ ] **Step 1: 실패하는 테스트 작성**

```tsx
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
});
```

- [ ] **Step 2: 실패 확인**

Run: `npm test -- FunnelStage`
Expected: FAIL (모듈 미존재).

- [ ] **Step 3: `FunnelStage.tsx` 구현**

```tsx
"use client";

import { Check, AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";
import type { StageStatus } from "@/lib/builder/stageStatus";

interface FunnelStageProps {
  id: string;
  stepNum: number;
  title: string;
  status: StageStatus;
  showConnector?: boolean;
  children: ReactNode;
}

export function FunnelStage({
  id,
  stepNum,
  title,
  status,
  showConnector = true,
  children,
}: FunnelStageProps) {
  return (
    <section id={`stage-${id}`} aria-label={title} className="scroll-mt-24">
      <div className="card">
        <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100 dark:border-slate-700">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-semibold flex-shrink-0">
            {stepNum}
          </span>
          <h2 className="text-subheading text-slate-900 dark:text-white flex-1">{title}</h2>
          <StatusChip status={status} />
        </div>
        {children}
      </div>
      {showConnector && (
        <div className="flex justify-center py-1" aria-hidden="true">
          <div className="w-px h-4 bg-gradient-to-b from-slate-300 to-transparent dark:from-slate-600" />
        </div>
      )}
    </section>
  );
}

function StatusChip({ status }: { status: StageStatus }) {
  if (status === "complete") {
    return (
      <span
        data-testid="stage-status-complete"
        className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400"
      >
        <Check className="w-3.5 h-3.5" aria-hidden="true" /> 완료
      </span>
    );
  }
  if (status === "warning") {
    return (
      <span
        data-testid="stage-status-warning"
        className="inline-flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400"
      >
        <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" /> 조건 없음
      </span>
    );
  }
  return (
    <span
      data-testid="stage-status-empty"
      className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 dark:text-slate-500"
    >
      비어있음
    </span>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `npm test -- FunnelStage`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add src/components/builder/FunnelStage.tsx src/components/builder/FunnelStage.test.tsx
git commit -m "feat(builder-ui): add FunnelStage card component"
```

---

## Task 3: `StageRail` 컴포넌트 (TDD)

**Files:**
- Create: `src/components/builder/StageRail.tsx`
- Test: `src/components/builder/StageRail.test.tsx`

- [ ] **Step 1: 실패하는 테스트 작성**

```tsx
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
```

- [ ] **Step 2: 실패 확인**

Run: `npm test -- StageRail`
Expected: FAIL (모듈 미존재).

- [ ] **Step 3: `StageRail.tsx` 구현**

```tsx
"use client";

import { Check, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StageId, StageStatus } from "@/lib/builder/stageStatus";

export interface StageRailItem {
  id: StageId;
  stepNum: number;
  shortLabel: string;
  status: StageStatus;
}

interface StageRailProps {
  stages: StageRailItem[];
  activeId: StageId | null;
  onJump: (id: StageId) => void;
}

export function StageRail({ stages, activeId, onJump }: StageRailProps) {
  return (
    <nav
      aria-label="전략 빌더 단계"
      className="hidden lg:flex flex-col gap-1 sticky top-20 self-start"
    >
      {stages.map((s) => {
        const isActive = s.id === activeId;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onJump(s.id)}
            aria-current={isActive ? "step" : undefined}
            className={cn(
              "flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors text-left focus-ring whitespace-nowrap",
              isActive && "bg-primary/10 text-primary",
              !isActive &&
                s.status === "complete" &&
                "text-emerald-600 dark:text-emerald-400 hover:bg-slate-50 dark:hover:bg-slate-800",
              !isActive &&
                s.status === "warning" &&
                "text-amber-600 dark:text-amber-400 hover:bg-slate-50 dark:hover:bg-slate-800",
              !isActive &&
                s.status === "empty" &&
                "text-slate-400 dark:text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800",
            )}
          >
            {s.status === "complete" ? (
              <Check className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
            ) : s.status === "warning" ? (
              <AlertTriangle className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
            ) : (
              <span className="w-3 text-center flex-shrink-0">{s.stepNum}</span>
            )}
            <span>{s.shortLabel}</span>
          </button>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `npm test -- StageRail`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add src/components/builder/StageRail.tsx src/components/builder/StageRail.test.tsx
git commit -m "feat(builder-ui): add StageRail navigation"
```

---

## Task 4: `BuilderActionBar` 컴포넌트 (TDD)

**Files:**
- Create: `src/components/builder/BuilderActionBar.tsx`
- Test: `src/components/builder/BuilderActionBar.test.tsx`

- [ ] **Step 1: 실패하는 테스트 작성**

```tsx
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
    expect(screen.getByRole("button", { name: /페이퍼로 등록/ })).toBeDisabled();
  });

  it("유효하면 onSave/onRegister를 호출한다", async () => {
    const onSave = vi.fn();
    const onRegister = vi.fn();
    render(<BuilderActionBar {...baseProps} onSave={onSave} onRegister={onRegister} />);
    await userEvent.click(screen.getByRole("button", { name: /저장/ }));
    await userEvent.click(screen.getByRole("button", { name: /페이퍼로 등록/ }));
    expect(onSave).toHaveBeenCalledOnce();
    expect(onRegister).toHaveBeenCalledOnce();
  });

  it("등록 중에는 등록 버튼이 비활성", () => {
    render(<BuilderActionBar {...baseProps} registering={true} />);
    expect(screen.getByRole("button", { name: /페이퍼로 등록/ })).toBeDisabled();
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
```

- [ ] **Step 2: 실패 확인**

Run: `npm test -- BuilderActionBar`
Expected: FAIL (모듈 미존재).

- [ ] **Step 3: `BuilderActionBar.tsx` 구현**

```tsx
"use client";

import { Save, Play, Loader2, CheckCircle2, X } from "lucide-react";

interface BuilderActionBarProps {
  isValid: boolean;
  validationErrors: string[];
  registering: boolean;
  lastRegistered: { name: string } | null;
  onSave: () => void;
  onRegister: () => void;
  onDismissGuidance: () => void;
}

export function BuilderActionBar({
  isValid,
  validationErrors,
  registering,
  lastRegistered,
  onSave,
  onRegister,
  onDismissGuidance,
}: BuilderActionBarProps) {
  const disabledReason = isValid ? undefined : validationErrors.join("\n");

  return (
    <div className="sticky bottom-0 z-10 mt-4 -mx-4 px-4 py-3 bg-white/90 dark:bg-slate-900/90 backdrop-blur border-t border-slate-200 dark:border-slate-700">
      {lastRegistered && (
        <div
          role="status"
          className="mb-3 flex items-start gap-2 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 px-3 py-2"
        >
          <CheckCircle2
            className="w-4 h-4 text-emerald-600 dark:text-emerald-400 mt-0.5 flex-shrink-0"
            aria-hidden="true"
          />
          <div className="flex-1 text-xs text-emerald-800 dark:text-emerald-200">
            <p className="font-medium">
              &apos;{lastRegistered.name}&apos; 전략이 페이퍼에 등록되었습니다 (비활성).
            </p>
            <p className="mt-0.5 text-emerald-700/80 dark:text-emerald-300/80">
              활성화는 운영자 작업이며 orchestrator 재적용 후 반영됩니다. 체결·포지션은 대시보드에서 모니터링하세요.
            </p>
          </div>
          <button
            type="button"
            onClick={onDismissGuidance}
            aria-label="안내 닫기"
            className="text-emerald-600/60 hover:text-emerald-700 dark:hover:text-emerald-300 flex-shrink-0"
          >
            <X className="w-3.5 h-3.5" aria-hidden="true" />
          </button>
        </div>
      )}
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onSave}
          disabled={!isValid}
          title={disabledReason}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors text-slate-700 bg-slate-100 hover:bg-slate-200 dark:text-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed focus-ring"
        >
          <Save className="w-4 h-4" aria-hidden="true" />
          저장
        </button>
        <button
          type="button"
          onClick={onRegister}
          disabled={!isValid || registering}
          title={disabledReason}
          className="flex items-center gap-1.5 px-5 py-2 text-sm font-medium rounded-lg transition-colors bg-primary text-white hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed focus-ring"
        >
          {registering ? (
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
          ) : (
            <Play className="w-4 h-4" aria-hidden="true" />
          )}
          페이퍼로 등록
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `npm test -- BuilderActionBar`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add src/components/builder/BuilderActionBar.tsx src/components/builder/BuilderActionBar.test.tsx
git commit -m "feat(builder-ui): add BuilderActionBar with register guidance"
```

---

## Task 5: `CustomStrategyList` 등록 피드백 `alert()` → toast (TDD)

좌측 "내 전략" 리스트의 per-strategy 등록도 `alert()` 대신 toast 사용 (액션바와 일관).

**Files:**
- Modify: `src/components/builder/CustomStrategyList.tsx`
- Test: `src/components/builder/CustomStrategyList.test.tsx`

- [ ] **Step 1: 실패하는 테스트 작성**

`registerPaperStrategy`/`listRegisteredStrategies`는 `@/lib/api`에서 import되므로 모듈 모킹. toast는 `ToastProvider`로 감싸 DOM에 노출되는 메시지를 검증.
```tsx
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
    await userEvent.click(screen.getByRole("button", { name: /더보기|menu|MoreVertical/i }).catch?.(() => {}) ?? screen.getAllByRole("button")[1]);
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
    await userEvent.click(screen.getAllByRole("button")[1]);
    await userEvent.click(screen.getByRole("button", { name: /페이퍼로 등록/ }));
    await waitFor(() => expect(window.alert).not.toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText(/등록 실패/)).toBeInTheDocument());
  });
});
```

> 참고: 메뉴 토글 버튼은 접근명이 없으므로(`MoreVertical` 아이콘) `screen.getAllByRole("button")[1]`로 두 번째 버튼(메뉴 토글)을 클릭한다. 구현 단계에서 메뉴 버튼에 `aria-label="전략 메뉴"`를 추가하면 셀렉터를 `getByRole("button", { name: "전략 메뉴" })`로 안정화할 수 있다 — Step 3에서 함께 적용.

- [ ] **Step 2: 실패 확인**

Run: `npm test -- CustomStrategyList`
Expected: FAIL (현재 `alert()` 사용 → `window.alert`가 호출되어 단언 실패, toast 텍스트 없음).

- [ ] **Step 3: 구현 — `alert()` → toast 교체**

`src/components/builder/CustomStrategyList.tsx` 수정:

(a) import에 `useToast` 추가:
```tsx
import { useToast } from "@/components/ui";
```

(b) 컴포넌트 본문 상단(다른 hook 옆)에 추가:
```tsx
  const toast = useToast();
```

(c) 메뉴 토글 버튼에 `aria-label` 추가 (셀렉터 안정화). 기존:
```tsx
              <button
                onClick={(e) => handleMenuToggle(strategy.id, e)}
                className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
              >
                <MoreVertical className="w-4 h-4" />
              </button>
```
→ `<button ...>`에 `aria-label="전략 메뉴"` 추가.

(d) `handleRegister`의 두 `alert(...)`를 toast로 교체. 기존:
```tsx
        await registerPaperStrategy({
          builder_state: strategy.state,
        });
        await refreshRegistered();
        alert(
          `'${strategy.name}' 전략이 페이퍼 트레이딩에 등록되었습니다.\n` +
            "기본 상태는 비활성입니다. 활성화는 별도 작업이 필요합니다.",
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        alert(`등록 실패: ${msg}`);
      } finally {
```
→
```tsx
        await registerPaperStrategy({
          builder_state: strategy.state,
        });
        await refreshRegistered();
        toast.success(
          `'${strategy.name}' 전략을 페이퍼에 등록했습니다 (비활성). 활성화는 운영자 작업입니다.`,
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        toast.error(`등록 실패: ${msg}`);
      } finally {
```

(e) `useCallback(handleRegister, [...])`의 의존성 배열에 `toast` 추가: `[refreshRegistered, toast]`.

- [ ] **Step 4: 통과 확인**

Run: `npm test -- CustomStrategyList`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add src/components/builder/CustomStrategyList.tsx src/components/builder/CustomStrategyList.test.tsx
git commit -m "refactor(builder-ui): CustomStrategyList register feedback uses toast"
```

---

## Task 6: `page.tsx` 깔때기 재구성 + index export

스텝퍼를 제거하고 세로 깔때기 피드 + StageRail + BuilderActionBar로 재배선. 큰 리팩토링이므로 (a) export 추가 → (b) page 재작성 순으로 진행. page 통합은 유닛테스트 대신 `tsc`/`lint`/`build`/수동으로 검증(스펙 §7).

**Files:**
- Modify: `src/components/builder/index.ts`
- Modify: `src/app/builder/page.tsx`

- [ ] **Step 1: `index.ts`에 신규 컴포넌트 export 추가**

`src/components/builder/index.ts` 끝에 추가:
```ts
export { FunnelStage } from "./FunnelStage";
export { StageRail, type StageRailItem } from "./StageRail";
export { BuilderActionBar } from "./BuilderActionBar";
```

- [ ] **Step 2: `page.tsx` import 갱신**

상단 import에서 스텝퍼용 아이콘(`ArrowRight`, `ArrowLeft`, `Check`, `AlertTriangle`) 제거하고, builder 컴포넌트 import에 신규 3개 추가, stageStatus 헬퍼 import 추가.

builder import 블록을 다음으로 교체:
```tsx
import {
  IndicatorSelector,
  ConditionBuilder,
  RiskManager,
  MetadataEditor,
  PreviewPanel,
  CustomStrategyList,
  ActiveStrategiesPanel,
  FunnelStage,
  StageRail,
  BuilderActionBar,
  type StageRailItem,
} from "@/components/builder";
import {
  computeStageStatuses,
  firstIncompleteStageId,
  type StageId,
} from "@/lib/builder/stageStatus";
import { registerPaperStrategy } from "@/lib/api";
```
그리고 `lucide-react` import에서 `ArrowRight, ArrowLeft, Check, AlertTriangle` 제거(나머지 `Upload, Sparkles, Save, BarChart3, Loader2, Info`는 유지).

- [ ] **Step 3: 스텝퍼 상태/네비 로직 제거 + 스테이지 메타 추가**

다음을 **삭제**한다:
- `type BuilderTab = ...` 와 `const STEPS = [...] as const;`
- `const [builderTab, setBuilderTab] = useState<BuilderTab>("indicators");`
- `getStepStatus` useCallback 전체
- `currentStepIndex`, `goToNextStep`, `goToPrevStep` useCallback 전체
- 키보드 네비 `useEffect`(Alt+ArrowLeft/Right) 전체

다음을 **추가**한다 (다른 useState 옆):
```tsx
  const [activeStage, setActiveStage] = useState<StageId>("metadata");
  const [registering, setRegistering] = useState(false);
  const [lastRegistered, setLastRegistered] = useState<{ name: string } | null>(null);

  const STAGES = useMemo(
    () =>
      [
        { id: "metadata", stepNum: 1, label: "전략 정보", shortLabel: "정보" },
        { id: "indicators", stepNum: 2, label: "지표 선택", shortLabel: "지표" },
        { id: "entry", stepNum: 3, label: "진입 조건", shortLabel: "진입" },
        { id: "exit", stepNum: 4, label: "청산 조건", shortLabel: "청산" },
        { id: "risk", stepNum: 5, label: "리스크 관리", shortLabel: "리스크" },
      ] as const,
    [],
  );

  const stageStatuses = useMemo(
    () => computeStageStatuses(builder.state),
    [builder.state],
  );

  const railStages: StageRailItem[] = STAGES.map((s) => ({
    id: s.id,
    stepNum: s.stepNum,
    shortLabel: s.shortLabel,
    status: stageStatuses[s.id],
  }));

  const handleJumpToStage = useCallback((id: StageId) => {
    setActiveStage(id);
    document
      .getElementById(`stage-${id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const handleRegisterDraft = useCallback(async () => {
    if (!builder.isValid) {
      toast.error(builder.validationErrors.join("\n"));
      const first = firstIncompleteStageId(builder.state);
      if (first) handleJumpToStage(first);
      return;
    }
    setRegistering(true);
    try {
      const result = await registerPaperStrategy({ builder_state: builder.state });
      setLastRegistered({ name: result.name });
      toast.success(`'${result.name}' 전략을 페이퍼에 등록했습니다.`);
    } catch (err) {
      toast.error(`등록 실패: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRegistering(false);
    }
  }, [builder, toast, handleJumpToStage]);
```

- [ ] **Step 4: `handleSaveCustomStrategy`에 invalid 시 스테이지 점프 추가**

기존:
```tsx
  const handleSaveCustomStrategy = useCallback(() => {
    if (!builder.isValid) {
      toast.error(builder.validationErrors.join("\n"));
      return;
    }
    localStrategies.save(builder.state);
    toast.success(`"${builder.state.metadata.name}" 전략이 저장되었습니다.`);
  }, [builder, localStrategies, toast]);
```
→
```tsx
  const handleSaveCustomStrategy = useCallback(() => {
    if (!builder.isValid) {
      toast.error(builder.validationErrors.join("\n"));
      const first = firstIncompleteStageId(builder.state);
      if (first) handleJumpToStage(first);
      return;
    }
    localStrategies.save(builder.state);
    toast.success(`"${builder.state.metadata.name}" 전략이 저장되었습니다.`);
  }, [builder, localStrategies, toast, handleJumpToStage]);
```

- [ ] **Step 5: `handleCreateNew`의 스텝퍼 점프 제거**

기존 `setBuilderTab("metadata");`를 `handleJumpToStage("metadata");`로 교체.

- [ ] **Step 6: 우측 빌더 컬럼 JSX 교체**

`{/* Right: Visual Builder */}` `<div className="lg:col-span-2">` 내부 전체(`<div className="grid lg:grid-cols-2 gap-4">` ... 닫는 `</div>`까지, 즉 Builder Panel + Preview Panel 블록)를 다음으로 교체:
```tsx
        {/* Right: Funnel Feed + Preview */}
        <div className="lg:col-span-2 grid lg:grid-cols-[auto_minmax(0,1fr)_minmax(0,340px)] gap-4">
          {/* Left mini-rail */}
          <StageRail stages={railStages} activeId={activeStage} onJump={handleJumpToStage} />

          {/* Funnel feed */}
          <div className={cn("min-w-0", showPreview && "hidden lg:block")}>
            {/* Asset Class Toggle */}
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">자산군</span>
              <div role="group" aria-label="자산군" className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5">
                {(["stock", "futures"] as const).map((ac) => (
                  <button
                    key={ac}
                    type="button"
                    aria-pressed={builder.state.assetClass === ac}
                    onClick={() => builder.setAssetClass(ac)}
                    className={cn(
                      "px-3 py-1 text-sm rounded-md transition-colors",
                      builder.state.assetClass === ac
                        ? "bg-blue-600 text-white"
                        : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
                    )}
                  >
                    {ac === "stock" ? "주식" : "선물"}
                  </button>
                ))}
              </div>
              {builder.state.assetClass === "futures" && (
                <span className="text-xs text-amber-600 dark:text-amber-400">
                  선물은 long-only (Phase 1) · EOD 15:15·하드스톱 자동 적용
                </span>
              )}
            </div>

            <div className="space-y-1">
              <FunnelStage id="metadata" stepNum={1} title="전략 정보" status={stageStatuses.metadata}>
                <MetadataEditor metadata={builder.state.metadata} onChange={builder.setMetadata} />
              </FunnelStage>

              <FunnelStage id="indicators" stepNum={2} title="지표 선택" status={stageStatuses.indicators}>
                <IndicatorSelector
                  selectedIndicators={builder.state.indicators}
                  onAddIndicator={builder.addIndicatorWithAutoConditions}
                  onUpdateIndicator={builder.updateIndicator}
                  onRemoveIndicator={builder.removeIndicator}
                  createIndicator={builder.createIndicator}
                  assetClass={builder.state.assetClass}
                />
              </FunnelStage>

              <FunnelStage id="entry" stepNum={3} title="진입 조건" status={stageStatuses.entry}>
                <ConditionBuilder
                  title="진입 조건"
                  conditionGroup={builder.state.entry}
                  indicators={builder.state.indicators}
                  onAddCondition={builder.addEntryCondition}
                  onAddIndicator={builder.addIndicator}
                  createIndicator={builder.createIndicator}
                  onUpdateCondition={builder.updateEntryCondition}
                  onRemoveCondition={builder.removeEntryCondition}
                  onReorderConditions={builder.reorderEntryConditions}
                  onSetLogic={builder.setEntryLogic}
                />
              </FunnelStage>

              <FunnelStage id="exit" stepNum={4} title="청산 조건" status={stageStatuses.exit}>
                <ConditionBuilder
                  title="청산 조건"
                  conditionGroup={builder.state.exit}
                  indicators={builder.state.indicators}
                  onAddCondition={builder.addExitCondition}
                  onAddIndicator={builder.addIndicator}
                  createIndicator={builder.createIndicator}
                  onUpdateCondition={builder.updateExitCondition}
                  onRemoveCondition={builder.removeExitCondition}
                  onReorderConditions={builder.reorderExitConditions}
                  onSetLogic={builder.setExitLogic}
                />
              </FunnelStage>

              <FunnelStage id="risk" stepNum={5} title="리스크 관리" status={stageStatuses.risk} showConnector={false}>
                <RiskManager risk={builder.state.risk} onChange={builder.setRisk} />
              </FunnelStage>
            </div>

            <BuilderActionBar
              isValid={builder.isValid}
              validationErrors={builder.validationErrors}
              registering={registering}
              lastRegistered={lastRegistered}
              onSave={handleSaveCustomStrategy}
              onRegister={handleRegisterDraft}
              onDismissGuidance={() => setLastRegistered(null)}
            />
          </div>

          {/* Preview Panel */}
          <div className={cn("card self-start sticky top-20", !showPreview && "hidden lg:block")}>
            {showPreview && (
              <button
                onClick={() => setShowPreview(false)}
                className="lg:hidden mb-3 text-sm text-slate-500 hover:text-slate-700"
              >
                &larr; 빌더로 돌아가기
              </button>
            )}
            <PreviewPanel
              yamlContent={builderYamlContent}
              pythonContent={pythonContent}
              pythonLoading={pythonLoading}
              pythonError={pythonError}
              onExport={handleExportYaml}
              onExportPython={handleExportPython}
              onRequestPython={handleRequestPython}
            />
          </div>
        </div>
```

- [ ] **Step 7: 타입체크**

Run: `npx tsc --noEmit`
Expected: 에러 없음. (자주 나오는 것: 미사용 import 잔존 → 제거. `STAGES` 항목의 `id` 리터럴이 `StageId`로 좁혀지는지 — `as const`로 OK.)

- [ ] **Step 8: 린트**

Run: `npm run lint`
Expected: 에러 없음. 미사용 변수/import 경고 정리.

- [ ] **Step 9: 빌드**

Run: `npm run build`
Expected: 빌드 성공.

- [ ] **Step 10: 전체 테스트**

Run: `npm test`
Expected: 모든 테스트 PASS.

- [ ] **Step 11: 커밋**

```bash
git add src/components/builder/index.ts src/app/builder/page.tsx
git commit -m "feat(builder-ui): restructure /builder into vertical funnel feed"
```

---

## Task 7: 수동 검증 + 최종 정리

**Files:** 없음 (검증·문서)

- [ ] **Step 1: 개발 서버 기동 (수동 확인)**

Run: `npm run dev` (포트 3100). 백엔드(FastAPI/Caddy 5080)가 떠 있어야 프리셋/등록 API가 동작. 운영자 공용 스택을 `docker compose down` 하지 말 것 — 이미 떠 있는 스택을 사용하거나 host-level로 기동.

- [ ] **Step 2: 수용 기준 수동 점검 (스펙 §9)**

브라우저 `/builder`에서 확인:
- 중앙이 세로 깔때기 피드로 렌더, 5개 스테이지가 한 스크롤로 모두 보임
- 좌측 StageRail chip 클릭 → 해당 스테이지로 스무스 스크롤, status 색상 표시
- 빈 전략 상태에서 "페이퍼로 등록" disabled + 첫 미충족 스테이지로 점프(검증 토스트)
- 유효 전략 작성 후 "페이퍼로 등록" → 성공 toast + 안내 카드(등록→활성화→모니터링)
- 좌측 "내 전략"에서 등록 시 alert 아님(toast)
- 프리뷰(YAML/Python), import/export, 프리셋/Active 패널 정상
- 모바일 뷰(폭 축소)에서 프리뷰 토글 + 세로 스크롤 정상

- [ ] **Step 3: 발견된 문제 수정**

수동 점검에서 레이아웃/배선 이슈 발견 시 수정하고 `npm run build` + `npm test` 재실행 후 커밋:
```bash
git add -A && git commit -m "fix(builder-ui): <발견 이슈 요약>"
```

- [ ] **Step 4: push + PR (CLAUDE.md 워크플로우)**

```bash
git push -u origin feat/builder-funnel-redesign
gh pr create --base main --head feat/builder-funnel-redesign \
  --title "feat(builder-ui): /builder 세로 깔때기 흐름 재구성 + 등록 UX 개선" \
  --body "<무엇/왜/테스트/수용기준 체크리스트 — 스펙·플랜 링크 포함>"
```
이후 `/code-review` 실행 → 리뷰 대응 → (사용자 승인 시) 머지.

---

## Self-Review (작성자 점검 완료)

**1. Spec coverage:**
- §3 레이아웃(3-컬럼+깔때기) → Task 6 Step 6 ✓
- §4.1 FunnelStage → Task 2 ✓ / §4.2 StageRail → Task 3 ✓ / §4.3 BuilderActionBar → Task 4 ✓
- §5.2 draft 직접 등록 → Task 6 `handleRegisterDraft` ✓ / §5.3 alert→toast+안내 → Task 4(안내카드)+Task 5(리스트)+Task 6(핸들러) ✓ / §5.4 enable 토글 범위 외 → 미구현(의도) ✓
- §6 검증 게이트+첫 미충족 점프 → Task 4(disabled)+Task 1(firstIncomplete)+Task 6(점프) ✓
- §7 vitest+RTL → Task 0; 페이지 통합 build/manual → Task 6/7 ✓
- §9 수용 기준 → Task 7 Step 2 ✓

**2. Placeholder scan:** 코드 스텝은 모두 실제 코드 포함. PR body만 `<...>` 자리표시(작성자 판단 영역) — 의도적.

**3. Type consistency:** `StageId`/`StageStatus`(Task 1) → FunnelStage/StageRail/page 동일 사용. `StageRailItem`(Task 3 export) → page Task 6 import 동일. `registerPaperStrategy`/`RegisteredStrategy.name`(실 시그니처) → handleRegisterDraft 일치. `useToast().{success,error}` 시그니처 일치. `INITIAL_STATE`/`StoredStrategy` 테스트 픽스처 실 타입 일치.
