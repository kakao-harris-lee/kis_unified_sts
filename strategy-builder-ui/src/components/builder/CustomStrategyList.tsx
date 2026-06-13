"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useToast } from "@/components/ui";
import {
  Plus,
  Trash2,
  Copy,
  Clock,
  MoreVertical,
  FileCode2,
  Play,
  Power,
  Radio,
  Receipt,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { StoredStrategy } from "@/types/builder";
import {
  registerPaperStrategy,
  listRegisteredStrategies,
  setRegisteredEnabled,
  unregisterStrategy,
  getRegisteredActivity,
  type RegisteredStrategy,
} from "@/lib/api";

interface CustomStrategyListProps {
  strategies: StoredStrategy[];
  selectedId: string | null;
  onSelect: (strategy: StoredStrategy) => void;
  onDelete: (id: string) => void;
  onDuplicate: (id: string) => void;
  onCreateNew: () => void;
  /**
   * Bump to force a refresh of the server-side registered roster — e.g. after
   * the BuilderActionBar registers the current canvas. Lets a sibling action
   * keep this unified list in sync without a shared query cache.
   */
  refreshSignal?: number;
}

type Lifecycle = "draft" | "registered" | "active";

interface StrategyRow {
  id: string;
  name: string;
  /** Local draft (present iff this strategy exists in this browser). */
  draft?: StoredStrategy;
  /** Server registration record (present iff registered to paper). */
  registered?: RegisteredStrategy;
  activity?: { signals: number; trades: number };
  status: Lifecycle;
  updatedAt?: string;
}

const STATUS_META: Record<
  Lifecycle,
  { label: string; className: string }
> = {
  active: {
    label: "활성",
    className:
      "text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30",
  },
  registered: {
    label: "등록됨",
    className: "text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30",
  },
  draft: {
    label: "드래프트",
    className:
      "text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800",
  },
};

const STATUS_ORDER: Record<Lifecycle, number> = {
  active: 0,
  registered: 1,
  draft: 2,
};

/**
 * Unified "내 전략" list: one row per strategy across its whole lifecycle —
 * local draft → registered (paper) → active (orchestrator pickup). Merges the
 * browser-local drafts with the server-side registered roster (keyed by id) so
 * a single strategy is never shown twice, and folds in the management actions
 * (register, enable/disable, unregister, activity) that previously lived in a
 * separate "등록된 전략" panel.
 */
export function CustomStrategyList({
  strategies,
  selectedId,
  onSelect,
  onDelete,
  onDuplicate,
  onCreateNew,
  refreshSignal = 0,
}: CustomStrategyListProps) {
  const toast = useToast();
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [registered, setRegistered] = useState<RegisteredStrategy[]>([]);
  const [activityById, setActivityById] = useState<
    Record<string, { signals: number; trades: number }>
  >({});
  const [busyId, setBusyId] = useState<string | null>(null);

  // Server-side registered roster + per-strategy activity. Best-effort: if the
  // dashboard is offline the list degrades to local drafts only.
  const refreshRegistered = useCallback(async () => {
    try {
      const [list, act] = await Promise.all([
        listRegisteredStrategies(),
        getRegisteredActivity().catch(() => ({ activity: [] })),
      ]);
      setRegistered(list.strategies);
      const byId: Record<string, { signals: number; trades: number }> = {};
      for (const a of act.activity) {
        byId[a.id] = { signals: a.signals, trades: a.trades };
      }
      setActivityById(byId);
    } catch {
      // Leave the previous roster in place; mutations surface their own errors.
    }
  }, []);

  useEffect(() => {
    void refreshRegistered();
  }, [refreshRegistered, refreshSignal]);

  const rows = useMemo<StrategyRow[]>(() => {
    const registeredById = new Map(registered.map((s) => [s.id, s]));
    const localById = new Map(strategies.map((s) => [s.id, s]));
    const ids = new Set<string>([...localById.keys(), ...registeredById.keys()]);
    const built = [...ids].map((id) => {
      const draft = localById.get(id);
      const reg = registeredById.get(id);
      const status: Lifecycle = reg
        ? reg.enabled
          ? "active"
          : "registered"
        : "draft";
      return {
        id,
        name: draft?.name ?? reg?.name ?? id,
        draft,
        registered: reg,
        activity: activityById[id],
        status,
        updatedAt: draft?.updatedAt ?? reg?.registered_at ?? undefined,
      };
    });
    built.sort(
      (a, b) =>
        STATUS_ORDER[a.status] - STATUS_ORDER[b.status] ||
        (b.updatedAt ?? "").localeCompare(a.updatedAt ?? ""),
    );
    return built;
  }, [strategies, registered, activityById]);

  const handleRegister = useCallback(
    async (row: StrategyRow, e: React.MouseEvent) => {
      e.stopPropagation();
      setMenuOpen(null);
      if (!row.draft) return; // can only register a strategy we hold locally
      setBusyId(row.id);
      try {
        await registerPaperStrategy({ builder_state: row.draft.state });
        await refreshRegistered();
        toast.success(
          `'${row.name}' 전략을 등록했습니다 (비활성). 활성화는 운영자 작업입니다.`,
        );
      } catch (err) {
        toast.error(`등록 실패: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setBusyId(null);
      }
    },
    [refreshRegistered, toast],
  );

  const handleToggle = useCallback(
    async (row: StrategyRow, e: React.MouseEvent) => {
      e.stopPropagation();
      setMenuOpen(null);
      if (!row.registered) return;
      setBusyId(row.id);
      try {
        await setRegisteredEnabled(row.id, !row.registered.enabled);
        await refreshRegistered();
      } catch (err) {
        toast.error(
          `상태 변경 실패: ${err instanceof Error ? err.message : String(err)}`,
        );
      } finally {
        setBusyId(null);
      }
    },
    [refreshRegistered, toast],
  );

  const handleUnregister = useCallback(
    async (row: StrategyRow, e: React.MouseEvent) => {
      e.stopPropagation();
      setMenuOpen(null);
      if (
        !confirm(
          `'${row.name}' 전략의 등록을 해제하시겠습니까?\n` +
            "YAML 파일이 삭제되어 오케스트레이터가 더 이상 로드하지 않습니다. " +
            "로컬 드래프트는 유지됩니다.",
        )
      ) {
        return;
      }
      setBusyId(row.id);
      try {
        await unregisterStrategy(row.id);
        await refreshRegistered();
      } catch (err) {
        toast.error(
          `등록 해제 실패: ${err instanceof Error ? err.message : String(err)}`,
        );
      } finally {
        setBusyId(null);
      }
    },
    [refreshRegistered, toast],
  );

  const formatDate = useCallback((dateStr: string) => {
    const date = new Date(dateStr);
    const days = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24));
    if (days <= 0) return "오늘";
    if (days === 1) return "어제";
    if (days < 7) return `${days}일 전`;
    return date.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  }, []);

  const handleMenuToggle = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setMenuOpen((prev) => (prev === id ? null : id));
  }, []);

  const handleSelectRow = useCallback(
    (row: StrategyRow) => {
      if (row.draft) {
        onSelect(row.draft);
      } else {
        toast.info(
          "이 전략의 원본 드래프트가 이 브라우저에 없어 편집할 수 없습니다. 활성/해제만 가능합니다.",
        );
      }
    },
    [onSelect, toast],
  );

  const handleDelete = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (confirm("이 로컬 드래프트를 삭제하시겠습니까? (등록된 전략에는 영향 없음)")) {
        onDelete(id);
      }
      setMenuOpen(null);
    },
    [onDelete],
  );

  const handleDuplicate = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      onDuplicate(id);
      setMenuOpen(null);
    },
    [onDuplicate],
  );

  const handleBackdropClick = useCallback(() => setMenuOpen(null), []);

  return (
    <div className="space-y-3">
      <button
        onClick={onCreateNew}
        className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg text-slate-500 hover:border-blue-400 hover:text-blue-500 hover:bg-blue-50/50 transition-all"
      >
        <Plus className="w-4 h-4" />
        <span className="text-sm font-medium">새 전략 만들기</span>
      </button>

      {rows.length > 0 ? (
        <div className="space-y-2">
          {rows.map((row) => {
            const meta = STATUS_META[row.status];
            const isBusy = busyId === row.id;
            const isRegistered = Boolean(row.registered);
            return (
              <div
                key={row.id}
                onClick={() => handleSelectRow(row)}
                className={cn(
                  "relative flex items-center justify-between px-3 py-3 rounded-lg cursor-pointer transition-all border",
                  selectedId === row.id
                    ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
                    : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 hover:border-blue-300 hover:shadow-sm",
                )}
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-slate-100 dark:bg-slate-700">
                    <FileCode2 className="w-4 h-4 text-slate-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <div className="font-medium text-sm text-slate-900 dark:text-white truncate">
                        {row.name}
                      </div>
                      <span
                        className={cn(
                          "inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded whitespace-nowrap",
                          meta.className,
                        )}
                      >
                        {meta.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      {row.updatedAt && (
                        <span className="inline-flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDate(row.updatedAt)}
                        </span>
                      )}
                      {isRegistered && (
                        <>
                          <span
                            className="inline-flex items-center gap-1"
                            title="발생 시그널 수"
                          >
                            <Radio className="w-3 h-3" />
                            {row.activity?.signals ?? 0}
                          </span>
                          <span
                            className="inline-flex items-center gap-1"
                            title="체결 수"
                          >
                            <Receipt className="w-3 h-3" />
                            {row.activity?.trades ?? 0}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <button
                  aria-label="전략 메뉴"
                  onClick={(e) => handleMenuToggle(row.id, e)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                >
                  {isBusy ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <MoreVertical className="w-4 h-4" />
                  )}
                </button>

                {menuOpen === row.id && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={handleBackdropClick} />
                    <div className="absolute right-0 top-full mt-1 z-20 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg py-1 min-w-[160px]">
                      {/* draft → register */}
                      {!isRegistered && row.draft && (
                        <button
                          onClick={(e) => handleRegister(row, e)}
                          disabled={isBusy}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
                        >
                          <Play className="w-3.5 h-3.5" />
                          등록
                        </button>
                      )}
                      {/* registered → enable/disable + unregister */}
                      {isRegistered && (
                        <>
                          <button
                            onClick={(e) => handleToggle(row, e)}
                            disabled={isBusy}
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
                          >
                            <Power
                              className={cn(
                                "w-3.5 h-3.5",
                                row.status === "active"
                                  ? "text-emerald-600"
                                  : "text-slate-400",
                              )}
                            />
                            {row.status === "active" ? "비활성화" : "활성화"}
                          </button>
                          <button
                            onClick={(e) => handleUnregister(row, e)}
                            disabled={isBusy}
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
                          >
                            <Power className="w-3.5 h-3.5" />
                            등록 해제
                          </button>
                        </>
                      )}
                      {/* local-draft-only actions */}
                      {row.draft && (
                        <>
                          <button
                            onClick={(e) => handleDuplicate(row.id, e)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
                          >
                            <Copy className="w-3.5 h-3.5" />
                            복제
                          </button>
                          <button
                            onClick={(e) => handleDelete(row.id, e)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            삭제
                          </button>
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8 text-slate-400">
          <FileCode2 className="w-10 h-10 mx-auto mb-2 opacity-40" />
          <p className="text-sm">전략이 없습니다</p>
          <p className="text-xs mt-1">새 전략을 만들어 저장하거나 등록하세요</p>
        </div>
      )}

      {rows.length > 0 && (
        <div className="text-xs text-slate-400 text-center">
          {rows.length}개 · 등록 {registered.length}개
        </div>
      )}
    </div>
  );
}
