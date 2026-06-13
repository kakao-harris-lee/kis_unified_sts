"use client";

import { Activity } from "lucide-react";

import { cn } from "@/lib/utils";
import { useActiveStrategies } from "@/hooks/dashboard/useStrategies";

interface ActiveStrategiesPanelProps {
  assetClass: "stock" | "futures";
}

/**
 * Read-only list of CODE strategies (entry_type !== "builder_v1") for the
 * selected asset class. These are defined in code/YAML and cannot be edited as
 * a BuilderState, so they live in their own read-only panel. Builder strategies
 * (which a user creates and registers) are shown in the unified "내 전략" list
 * instead — keeping the two namespaces from overlapping.
 */
export function ActiveStrategiesPanel({ assetClass }: ActiveStrategiesPanelProps) {
  const { strategies, isLoading, isError } = useActiveStrategies(assetClass);

  const codeStrategies = strategies.filter((s) => s.entry_type !== "builder_v1");
  const sorted = [...codeStrategies].sort(
    (a, b) => Number(b.enabled) - Number(a.enabled) || a.name.localeCompare(b.name),
  );

  return (
    <div className="card">
      <h2 className="text-subheading text-slate-900 dark:text-white mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4 text-primary" aria-hidden="true" />
        코드 전략
        <span className="text-caption text-slate-400 font-normal">
          ({codeStrategies.length})
        </span>
      </h2>
      <p className="text-xs text-slate-400 mb-3">
        코드로 정의된 {assetClass === "futures" ? "선물" : "주식"} 전략 (편집 불가)
      </p>
      <div className="space-y-2 max-h-[300px] overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <div className="text-center py-6 text-slate-400 text-sm">로딩 중...</div>
        ) : isError ? (
          <div className="text-center py-6 text-slate-400 text-sm">
            전략 목록을 불러오지 못했습니다
          </div>
        ) : sorted.length === 0 ? (
          <div className="text-center py-6 text-slate-400 text-sm">
            코드 전략이 없습니다
          </div>
        ) : (
          sorted.map((s) => (
            <div
              key={`${s.asset_class}-${s.name}`}
              className="flex items-start gap-3 px-3 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700"
            >
              <span
                className={cn(
                  "mt-1 w-2 h-2 rounded-full flex-shrink-0",
                  s.enabled ? "bg-green-500" : "bg-slate-300 dark:bg-slate-600",
                )}
                role="img"
                aria-label={s.enabled ? "활성" : "비활성"}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm text-slate-900 dark:text-white truncate">
                    {s.name}
                  </span>
                  <span className="px-1.5 py-0.5 text-[10px] font-medium rounded whitespace-nowrap bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                    코드 전략
                  </span>
                </div>
                <div className="text-xs text-slate-500 truncate">
                  {s.entry_type} → {s.exit_type}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
