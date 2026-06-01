# Builder Read-only Active-Strategy Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only "운용 전략" panel to the strategy builder (`/builder`) that lists runtime-registry strategies for the selected asset class, showing which are enabled and distinguishing builder vs. (read-only) code strategies.

**Architecture:** Frontend-only. Reuse the existing `GET /api/strategies` endpoint (already enumerates `config/strategies/{stock,futures}/` and returns `StrategyInfo` with `enabled`/`entry_type`/`exit_type`). Add a React Query hook that fetches with `enabled_only=false` filtered by asset, a presentational `ActiveStrategiesPanel` component, and render it in the builder's left column wired to the asset toggle. No backend changes.

**Tech Stack:** Next.js + React + TypeScript, @tanstack/react-query, Tailwind. Verify via `npx tsc --noEmit` + `npm run lint` + `npm run build` (no JS unit-test runner in this app).

**Spec:** `docs/superpowers/specs/2026-06-01-builder-readonly-strategy-panel-design.md`
**Branch:** `feat/builder-readonly-strategy-panel` (off `main`).

---

## Key facts (verified)
- `src/lib/dashboard/strategies.ts`: `strategiesApi.list({ asset_class?, enabled_only? }) → apiClient.get('/api/strategies', { params })` (axios-style, returns `{ data: { strategies } }`).
- `src/hooks/dashboard/useStrategies.ts` already defines and exports `StrategyInfo` (`name, asset_class, enabled, entry_type, exit_type, position_type, description`) and `StrategiesResponse` (`{ strategies: StrategyInfo[] }`), and uses `@tanstack/react-query`'s `useQuery`. QueryClientProvider is set up (`src/components/providers/Providers.tsx`).
- Backend `/api/strategies` `enabled_only` defaults to **True** (`services/dashboard/routes/strategies.py:51`) → the panel MUST pass `enabled_only: false` to see disabled strategies.
- `entry_type === "builder_v1"` ⇒ builder-authored strategy; anything else ⇒ code strategy (read-only, not representable as BuilderState).
- Builder left column (`src/app/builder/page.tsx`, the `lg:col-span-1 space-y-4` div, ~lines 318-396) renders two `card`s: "기본 전략" (presets) and "내 전략" (`<CustomStrategyList>`). The new panel is a third `card` appended after "내 전략".
- The asset toggle exposes `builder.state.assetClass` (`"stock" | "futures"`).
- Tailwind utility classes in use here: `card`, `text-subheading`, `text-caption`, `scrollbar-thin`, `focus-ring`, `text-primary`, `bg-primary/10`. `cn` from `@/lib/utils`.

---

## Task 1: `useActiveStrategies` hook

**Files:**
- Modify: `strategy-builder-ui/src/hooks/dashboard/useStrategies.ts`

- [ ] **Step 1: Add the hook (reuse existing `StrategyInfo`/`StrategiesResponse`)**

Append this to `src/hooks/dashboard/useStrategies.ts` (after the existing `useStrategies` function, before `export default`). It fetches with `enabled_only: false` so disabled strategies are included, filtered by asset class, keyed per-asset:

```typescript
/**
 * Active (runtime-registry) strategies for one asset class, INCLUDING disabled
 * ones (enabled_only=false) so the builder's read-only panel can show which are
 * enabled. Separate query key per asset so the asset toggle re-fetches.
 */
export function useActiveStrategies(assetClass: "stock" | "futures") {
  const { data, isLoading } = useQuery<StrategiesResponse>({
    queryKey: ["active-strategies", assetClass],
    queryFn: () =>
      strategiesApi
        .list({ asset_class: assetClass, enabled_only: false })
        .then((r) => r.data),
    staleTime: 60000,
  });

  return { strategies: data?.strategies ?? [], isLoading };
}
```

- [ ] **Step 2: Typecheck**

Run: `cd strategy-builder-ui && npx tsc --noEmit`
Expected: no new errors. (`StrategyInfo`/`StrategiesResponse`/`strategiesApi`/`useQuery` are all already imported/defined in this file.)

## Task 2: `ActiveStrategiesPanel` component

**Files:**
- Create: `strategy-builder-ui/src/components/builder/ActiveStrategiesPanel.tsx`

- [ ] **Step 1: Create the component**

```tsx
"use client";

import { Activity } from "lucide-react";

import { cn } from "@/lib/utils";
import { useActiveStrategies } from "@/hooks/dashboard/useStrategies";

interface ActiveStrategiesPanelProps {
  assetClass: "stock" | "futures";
}

/**
 * Read-only list of runtime-registry strategies for the selected asset class.
 * Surfaces which strategies are enabled. Code strategies (entry_type !==
 * "builder_v1") cannot be represented as a BuilderState, so they are shown
 * read-only with no edit/load action.
 */
export function ActiveStrategiesPanel({ assetClass }: ActiveStrategiesPanelProps) {
  const { strategies, isLoading } = useActiveStrategies(assetClass);

  // Enabled first, then by name.
  const sorted = [...strategies].sort(
    (a, b) => Number(b.enabled) - Number(a.enabled) || a.name.localeCompare(b.name),
  );

  return (
    <div className="card">
      <h2 className="text-subheading text-slate-900 dark:text-white mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4 text-primary" aria-hidden="true" />
        운용 전략
        <span className="text-caption text-slate-400 font-normal">
          ({strategies.length})
        </span>
      </h2>
      <p className="text-xs text-slate-400 mb-3">
        현재 등록된 {assetClass === "futures" ? "선물" : "주식"} 전략 (읽기 전용)
      </p>
      <div className="space-y-2 max-h-[300px] overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <div className="text-center py-6 text-slate-400 text-sm">로딩 중...</div>
        ) : strategies.length === 0 ? (
          <div className="text-center py-6 text-slate-400 text-sm">
            운용 전략이 없습니다
          </div>
        ) : (
          sorted.map((s) => {
            const isBuilder = s.entry_type === "builder_v1";
            return (
              <div
                key={`${s.asset_class}-${s.name}`}
                className="flex items-start gap-3 px-3 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700"
              >
                <span
                  className={cn(
                    "mt-1 w-2 h-2 rounded-full flex-shrink-0",
                    s.enabled ? "bg-green-500" : "bg-slate-300 dark:bg-slate-600",
                  )}
                  title={s.enabled ? "활성" : "비활성"}
                  aria-label={s.enabled ? "활성" : "비활성"}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm text-slate-900 dark:text-white truncate">
                      {s.name}
                    </span>
                    <span
                      className={cn(
                        "px-1.5 py-0.5 text-[10px] font-medium rounded whitespace-nowrap",
                        isBuilder
                          ? "bg-primary/10 text-primary"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400",
                      )}
                    >
                      {isBuilder ? "빌더 전략" : "코드 전략 · 읽기 전용"}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 truncate font-mono">
                    {s.entry_type} → {s.exit_type}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Export from the builder components barrel (if one exists)**

Check `strategy-builder-ui/src/components/builder/index.ts`. If it re-exports builder components (the page imports `{ ..., CustomStrategyList }` from `@/components/builder`), add:
```typescript
export { ActiveStrategiesPanel } from "./ActiveStrategiesPanel";
```
If there is no barrel, skip this step (the page will import directly from the file path in Task 3).

- [ ] **Step 3: Typecheck**

Run: `cd strategy-builder-ui && npx tsc --noEmit`
Expected: no errors.

## Task 3: Render the panel in the builder page

**Files:**
- Modify: `strategy-builder-ui/src/app/builder/page.tsx`

- [ ] **Step 1: Import the component**

In the `@/components/builder` import group (the block that imports `CustomStrategyList`, around lines 19-26), add `ActiveStrategiesPanel` to the named imports IF you added it to the barrel in Task 2.2. Otherwise add a direct import near the other component imports:
```tsx
import { ActiveStrategiesPanel } from "@/components/builder/ActiveStrategiesPanel";
```

- [ ] **Step 2: Render it after the "내 전략" card**

In the left column (`<div className="lg:col-span-1 space-y-4">`), immediately AFTER the closing `</div>` of the "내 전략" card (the `card` div that wraps `<CustomStrategyList .../>`, ends ~line 395) and BEFORE the left column's closing `</div>` (~line 396), insert:
```tsx
          {/* Active (runtime) strategies — read-only */}
          <ActiveStrategiesPanel assetClass={builder.state.assetClass} />
```
(`builder` is `useStrategyBuilder()`; `builder.state.assetClass` is `"stock" | "futures"`.)

- [ ] **Step 3: Typecheck + lint + build**

Run: `cd strategy-builder-ui && npx tsc --noEmit && npm run lint && npm run build`
Expected: build succeeds, no new type/lint errors.

## Task 4: Verify, commit, PR

- [ ] **Step 1: Manual smoke (optional, requires dashboard running)**

Open `/builder`, toggle 선물/주식. The "운용 전략" panel lists that asset class's strategies (e.g. futures: setup_a_gap_reversion ● 활성, setup_c_event_reaction ● 활성, bb_reversion_15m ● 활성, williams_r_15m ○ 비활성, ...). Code strategies show "코드 전략 · 읽기 전용"; any `builder_v1` shows "빌더 전략". No edit/load buttons on any row.

- [ ] **Step 2: Final verification**

Run: `cd strategy-builder-ui && npm run build`
Expected: `✓ Compiled successfully`.

- [ ] **Step 3: Commit (stage only the 3 files)**

```bash
git add strategy-builder-ui/src/hooks/dashboard/useStrategies.ts \
        strategy-builder-ui/src/components/builder/ActiveStrategiesPanel.tsx \
        strategy-builder-ui/src/app/builder/page.tsx
# include the barrel only if you modified it:
# git add strategy-builder-ui/src/components/builder/index.ts
git commit -m "feat(builder-ui): read-only active-strategy panel with enabled status

Lists runtime-registry strategies for the selected asset class in /builder,
showing which are enabled. Code strategies (non-builder_v1) are read-only since
they can't be represented as a BuilderState; builder_v1 strategies are labeled
'빌더 전략'. Reuses GET /api/strategies (enabled_only=false); no backend change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: Push & open PR**

```bash
git push -u origin feat/builder-readonly-strategy-panel
gh pr create --base main --title "feat(builder-ui): read-only active-strategy panel" \
  --body "Adds a read-only '운용 전략' panel to /builder showing runtime-registry strategies (config/strategies/{stock,futures}/) for the selected asset, with enabled badges. Code strategies are read-only (can't be represented as BuilderState). Reuses GET /api/strategies; no backend change. Spec: docs/superpowers/specs/2026-06-01-builder-readonly-strategy-panel-design.md"
```

---

## Acceptance criteria mapping (from spec §5)
| Spec criterion | Task |
|---|---|
| `/builder`에 "운용 전략" 읽기 전용 패널 | 2, 3 |
| 자산군 토글에 따라 선물/주식 목록 변경 | 1 (query key per asset) + 3 (`assetClass` prop) |
| enabled 여부 배지 표시 | 2 (● green / ○ gray) |
| builder_v1=빌더 전략, 그 외=코드 전략·읽기 전용 | 2 (badge by entry_type) |
| 코드 전략 편집/로드 액션 없음, 읽기 전용 | 2 (static rows, no buttons) |
| 백엔드 신규 엔드포인트 없음 | reuse `/api/strategies` |
| `npm run build` 그린, 회귀 없음 | 3, 4 |

## Notes
- Disabled strategies appear because the hook passes `enabled_only: false` (backend default is True).
- Offline/empty handled: `useQuery` failure → `strategies = []` → "운용 전략이 없습니다".
- Phase-1 scope: rows are display-only for BOTH builder and code strategies (no canvas-load). Loading a `builder_v1` strategy into the canvas for editing is a possible follow-up, out of scope here.
