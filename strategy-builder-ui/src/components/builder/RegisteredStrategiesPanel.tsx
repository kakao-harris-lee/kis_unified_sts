"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Trash2,
  Loader2,
  Activity,
  Radio,
  Receipt,
  RefreshCw,
  Rocket,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  listRegisteredStrategies,
  setRegisteredEnabled,
  unregisterStrategy,
  getRegisteredActivity,
  type RegisteredStrategy,
} from "@/lib/api";

/**
 * Paper-trading management panel for builder strategies that were
 * registered as YAML under config/strategies/built/.
 *
 * Surfaces three operations the builder draft list (CustomStrategyList)
 * intentionally does not: enable/disable the orchestrator pickup flag,
 * unregister (delete the YAML), and per-strategy signal/trade activity.
 *
 * Activity counts come from a separate endpoint that degrades to zero
 * when Redis/ClickHouse are unreachable, so the panel still renders the
 * roster even if the infra-backed counters are unavailable.
 */
export function RegisteredStrategiesPanel() {
  const [strategies, setStrategies] = useState<RegisteredStrategy[]>([]);
  const [activity, setActivity] = useState<Record<string, { signals: number; trades: number }>>({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [list, act] = await Promise.all([
        listRegisteredStrategies(),
        getRegisteredActivity().catch(() => ({ activity: [] })),
      ]);
      setStrategies(list.strategies);
      const byId: Record<string, { signals: number; trades: number }> = {};
      for (const a of act.activity) {
        byId[a.id] = { signals: a.signals, trades: a.trades };
      }
      setActivity(byId);
    } catch {
      // Best-effort: leave the previous roster in place if the dashboard
      // is momentarily offline.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleToggle = useCallback(
    async (strategy: RegisteredStrategy) => {
      setBusyId(strategy.id);
      try {
        const updated = await setRegisteredEnabled(strategy.id, !strategy.enabled);
        setStrategies((prev) =>
          prev.map((s) => (s.id === strategy.id ? { ...s, enabled: updated.enabled } : s)),
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        alert(`상태 변경 실패: ${msg}`);
      } finally {
        setBusyId(null);
      }
    },
    [],
  );

  const handleUnregister = useCallback(
    async (strategy: RegisteredStrategy) => {
      if (
        !confirm(
          `'${strategy.name}' 전략의 페이퍼 등록을 해제하시겠습니까?\n` +
            "YAML 파일이 삭제되며 오케스트레이터가 더 이상 로드하지 않습니다.",
        )
      ) {
        return;
      }
      setBusyId(strategy.id);
      try {
        await unregisterStrategy(strategy.id);
        setStrategies((prev) => prev.filter((s) => s.id !== strategy.id));
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        alert(`등록 해제 실패: ${msg}`);
      } finally {
        setBusyId(null);
      }
    },
    [],
  );

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-subheading text-slate-900 dark:text-white flex items-center gap-2">
          <Rocket className="w-4 h-4 text-primary" aria-hidden="true" />
          페이퍼 등록 전략
          <span className="text-caption text-slate-400 font-normal">({strategies.length})</span>
        </h2>
        <button
          onClick={() => void refresh()}
          disabled={loading}
          className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors focus-ring"
          aria-label="목록 새로고침"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} aria-hidden="true" />
          새로고침
        </button>
      </div>

      {loading && strategies.length === 0 ? (
        <div className="flex items-center justify-center py-8 text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin mr-2" aria-hidden="true" />
          <span className="text-sm">불러오는 중...</span>
        </div>
      ) : strategies.length === 0 ? (
        <div className="text-center py-8 text-slate-400">
          <Activity className="w-10 h-10 mx-auto mb-2 opacity-40" aria-hidden="true" />
          <p className="text-sm">페이퍼에 등록된 전략이 없습니다</p>
          <p className="text-xs mt-1">내 전략에서 &quot;페이퍼로 등록&quot;을 사용하세요</p>
        </div>
      ) : (
        <div className="space-y-2">
          {strategies.map((strategy) => {
            const counts = activity[strategy.id] ?? { signals: 0, trades: 0 };
            const isBusy = busyId === strategy.id;
            return (
              <div
                key={strategy.id}
                className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-slate-900 dark:text-white truncate">
                    {strategy.name}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-slate-500">
                    <span className="inline-flex items-center gap-1" title="발생 시그널 수">
                      <Radio className="w-3 h-3" aria-hidden="true" />
                      {counts.signals}
                    </span>
                    <span className="inline-flex items-center gap-1" title="체결 수">
                      <Receipt className="w-3 h-3" aria-hidden="true" />
                      {counts.trades}
                    </span>
                  </div>
                </div>

                {/* Enable/disable toggle */}
                <button
                  onClick={() => void handleToggle(strategy)}
                  disabled={isBusy}
                  role="switch"
                  aria-checked={strategy.enabled}
                  aria-label={`${strategy.name} ${strategy.enabled ? "비활성화" : "활성화"}`}
                  className={cn(
                    "relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors focus-ring disabled:opacity-50",
                    strategy.enabled ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600",
                  )}
                >
                  {isBusy ? (
                    <Loader2 className="w-3 h-3 mx-auto animate-spin text-white" aria-hidden="true" />
                  ) : (
                    <span
                      className={cn(
                        "inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform",
                        strategy.enabled ? "translate-x-[18px]" : "translate-x-1",
                      )}
                      aria-hidden="true"
                    />
                  )}
                </button>

                {/* Unregister */}
                <button
                  onClick={() => void handleUnregister(strategy)}
                  disabled={isBusy}
                  className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors disabled:opacity-50 focus-ring"
                  aria-label={`${strategy.name} 등록 해제`}
                  title="등록 해제"
                >
                  <Trash2 className="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
