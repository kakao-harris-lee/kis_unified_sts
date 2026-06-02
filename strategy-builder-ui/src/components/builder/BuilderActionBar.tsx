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
