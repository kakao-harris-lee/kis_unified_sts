"use client";

import type { TosBarsSummary } from '@/lib/dashboard/tosBars';
import { entryBlockers } from '@/lib/dashboard/tosDecision';
import Term from './Term';

/**
 * «오늘 진입을 막은 조건» — which entry condition was false most often.
 *
 * Horizontal bars, because the quantity is a share of one denominator and the
 * question is "which is longest": a pie would make five similar slices harder
 * to rank, and the denominator is already stated in words beside it.
 *
 * The share is the summary's own, over the bars the engine actually judged.
 * This panel never recomputes it from the rendered bars, which would quietly
 * include the withheld ones the exporter deliberately excluded.
 */
export default function BlockingConditions({
  summary,
}: {
  summary: TosBarsSummary | null | undefined;
}) {
  const blockers = entryBlockers(summary);
  if (!blockers.length) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        진입 규칙의 조건별 집계가 없습니다.
      </p>
    );
  }

  return (
    <div className="min-w-0 space-y-2">
      <h4 className="text-sm font-semibold">오늘 진입을 막은 조건</h4>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        <Term name="counted_bars">판단한 봉</Term> 중 각 조건이 거짓이었던 비율입니다. 가장 긴 줄이
        오늘의 병목입니다.
      </p>
      <ul className="space-y-2">
        {blockers.map((blocker) => (
          <li key={blocker.expression} className="min-w-0">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
              <span>
                <Term name={blocker.termKey}>{blocker.name}</Term>
              </span>
              <span className="tabular-nums text-slate-600 dark:text-slate-300">
                {blocker.failedPct == null ? '알 수 없음' : `${blocker.failedPct.toFixed(1)}%`}
                {blocker.failedBars != null && blocker.bars != null
                  ? ` · ${blocker.failedBars}/${blocker.bars}봉 거짓`
                  : ''}
              </span>
            </div>
            <div
              role="img"
              aria-label={`${blocker.name} 거짓 비율 ${
                blocker.failedPct == null ? '알 수 없음' : `${blocker.failedPct.toFixed(1)}퍼센트`
              }`}
              className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
            >
              <div
                className="h-2 rounded-full bg-amber-400 dark:bg-amber-500"
                style={{ width: `${Math.min(100, Math.max(0, blocker.failedPct ?? 0))}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
