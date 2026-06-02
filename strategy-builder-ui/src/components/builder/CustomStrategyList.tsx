"use client";

import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/components/ui";
import {
  Plus,
  Trash2,
  Copy,
  Clock,
  MoreVertical,
  FileCode2,
  Play,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { StoredStrategy } from "@/types/builder";
import {
  registerPaperStrategy,
  listRegisteredStrategies,
} from "@/lib/api";

interface CustomStrategyListProps {
  strategies: StoredStrategy[];
  selectedId: string | null;
  onSelect: (strategy: StoredStrategy) => void;
  onDelete: (id: string) => void;
  onDuplicate: (id: string) => void;
  onCreateNew: () => void;
}

export function CustomStrategyList({
  strategies,
  selectedId,
  onSelect,
  onDelete,
  onDuplicate,
  onCreateNew,
}: CustomStrategyListProps) {
  const toast = useToast();
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  // Track which builder IDs have a corresponding YAML under
  // config/strategies/built/<id>.yaml so we can show a "registered" badge
  // and avoid double-registering. Refreshes on mount and after any
  // register call.
  const [registeredIds, setRegisteredIds] = useState<Set<string>>(new Set());
  const [registeringId, setRegisteringId] = useState<string | null>(null);

  const refreshRegistered = useCallback(async () => {
    try {
      const resp = await listRegisteredStrategies();
      setRegisteredIds(new Set(resp.strategies.map((s) => s.id)));
    } catch {
      // Best-effort. If the dashboard is offline the list stays empty;
      // register attempts will surface their own error toast.
    }
  }, []);

  useEffect(() => {
    void refreshRegistered();
  }, [refreshRegistered]);

  const handleRegister = useCallback(
    async (strategy: StoredStrategy, e: React.MouseEvent) => {
      e.stopPropagation();
      setMenuOpen(null);
      // builder_state now carries assetClass (stock/futures); the backend
      // routes futures to contract sizing + auto-enforced exit safety. Phase 1
      // futures registers as 1 contract (backend default).
      setRegisteringId(strategy.id);
      try {
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
        setRegisteringId(null);
      }
    },
    [refreshRegistered, toast],
  );

  const formatDate = useCallback((dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return "오늘";
    } else if (days === 1) {
      return "어제";
    } else if (days < 7) {
      return `${days}일 전`;
    } else {
      return date.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
    }
  }, []);

  const handleMenuToggle = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setMenuOpen((prev) => (prev === id ? null : id));
  }, []);

  const handleDelete = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (confirm("이 전략을 삭제하시겠습니까?")) {
        onDelete(id);
      }
      setMenuOpen(null);
    },
    [onDelete]
  );

  const handleDuplicate = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      onDuplicate(id);
      setMenuOpen(null);
    },
    [onDuplicate]
  );

  // Close menu when clicking outside
  const handleBackdropClick = useCallback(() => {
    setMenuOpen(null);
  }, []);

  return (
    <div className="space-y-3">
      {/* Create New Button */}
      <button
        onClick={onCreateNew}
        className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg text-slate-500 hover:border-blue-400 hover:text-blue-500 hover:bg-blue-50/50 transition-all"
      >
        <Plus className="w-4 h-4" />
        <span className="text-sm font-medium">새 전략 만들기</span>
      </button>

      {/* Strategy List */}
      {strategies.length > 0 ? (
        <div className="space-y-2">
          {strategies.map((strategy) => (
            <div
              key={strategy.id}
              onClick={() => onSelect(strategy)}
              className={cn(
                "relative flex items-center justify-between px-3 py-3 rounded-lg cursor-pointer transition-all border",
                selectedId === strategy.id
                  ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
                  : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 hover:border-blue-300 hover:shadow-sm"
              )}
            >
              {/* Info */}
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-slate-100 dark:bg-slate-700">
                  <FileCode2 className="w-4 h-4 text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <div className="font-medium text-sm text-slate-900 dark:text-white truncate">
                      {strategy.name}
                    </div>
                    {registeredIds.has(strategy.id) && (
                      <span
                        title="페이퍼 트레이딩에 등록됨"
                        className="inline-flex items-center gap-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 px-1.5 py-0.5 rounded"
                      >
                        <CheckCircle2 className="w-2.5 h-2.5" />
                        등록됨
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-xs text-slate-500">
                    <Clock className="w-3 h-3" />
                    <span>{formatDate(strategy.updatedAt)}</span>
                  </div>
                </div>
              </div>

              {/* Menu Button */}
              <button
                aria-label="전략 메뉴"
                onClick={(e) => handleMenuToggle(strategy.id, e)}
                className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
              >
                <MoreVertical className="w-4 h-4" />
              </button>

              {/* Dropdown Menu */}
              {menuOpen === strategy.id && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={handleBackdropClick}
                  />
                  <div className="absolute right-0 top-full mt-1 z-20 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg py-1 min-w-[140px]">
                    <button
                      onClick={(e) => handleRegister(strategy, e)}
                      disabled={
                        registeringId === strategy.id ||
                        registeredIds.has(strategy.id)
                      }
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {registeringId === strategy.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : registeredIds.has(strategy.id) ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                      {registeredIds.has(strategy.id)
                        ? "등록됨"
                        : "페이퍼로 등록"}
                    </button>
                    <button
                      onClick={(e) => handleDuplicate(strategy.id, e)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
                    >
                      <Copy className="w-3.5 h-3.5" />
                      복제
                    </button>
                    <button
                      onClick={(e) => handleDelete(strategy.id, e)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      삭제
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-slate-400">
          <FileCode2 className="w-10 h-10 mx-auto mb-2 opacity-40" />
          <p className="text-sm">저장된 전략이 없습니다</p>
          <p className="text-xs mt-1">새 전략을 만들어 저장하세요</p>
        </div>
      )}

      {/* Storage Info */}
      {strategies.length > 0 && (
        <div className="text-xs text-slate-400 text-center">
          {strategies.length}개 저장됨
        </div>
      )}
    </div>
  );
}
