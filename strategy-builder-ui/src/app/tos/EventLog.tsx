"use client";

import config from '@/config/tos-control-plane.json';
import type { TosBarsBar, TosBarsSummary } from '@/lib/dashboard/tosBars';
import { barGate } from '@/lib/dashboard/tosDecision';
import { glossaryLabel } from '@/lib/dashboard/tosGlossary';
import { AsOf, Badge } from './marks';
import Term from './Term';

interface EventLogProps {
  bars: TosBarsBar[];
  summary: TosBarsSummary | null | undefined;
}

interface EventRun {
  code: string;
  reason: string;
  step: string | null;
  label: string;
  detail: string | null;
  firstTime: string | null;
  lastTime: string | null;
  count: number;
}

/**
 * The session's halts and withheld bars, in time order, run-length collapsed.
 *
 * One row per stretch of the same code rather than one per bar: a stock tenant
 * records 315 bars of the same «승인 없음» in a day, and 315 identical lines
 * would bury the two events that were different.
 */
export function eventRuns(bars: TosBarsBar[]): EventRun[] {
  const runs: EventRun[] = [];
  for (const bar of bars) {
    const gate = barGate(bar);
    if (!gate) continue;
    const code = gate.step ? `${gate.reason}@${gate.step}` : gate.reason;
    const last = runs[runs.length - 1];
    if (last && last.code === code) {
      last.count += 1;
      last.lastTime = bar.time_kst ?? last.lastTime;
      last.detail ??= gate.detail;
      continue;
    }
    runs.push({
      code,
      reason: gate.reason,
      step: gate.step,
      label: gate.label,
      detail: gate.detail,
      firstTime: bar.time_kst ?? null,
      lastTime: bar.time_kst ?? null,
      count: 1,
    });
  }
  return runs;
}

/**
 * «무슨 일이 있었나» — every stop, with the code it was recorded under AND the
 * plain-Korean name of it, never one without the other.
 *
 * The raw code stays on screen because it is what `sts tos inspect` and the
 * evidence stream say; the Korean name is what makes it readable. Dropping
 * either would cost the operator a translation step in one direction or the
 * other.
 */
export default function EventLog({ bars, summary }: EventLogProps) {
  const runs = eventRuns(bars);
  const shown = runs.slice(0, config.eventLogMaxRows);
  const withheld = summary?.withheld_bars ?? null;
  const substituted = summary?.substituted_bars ?? null;

  return (
    <section
      aria-label="사건 기록"
      className="min-w-0 space-y-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="min-w-0">
        <h2 className="font-semibold">사건 기록</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          무슨 일이 있었나 — 이 세션에서 판단을 멈추거나 주문을 막은 기록을 시간 순으로 봅니다.
        </p>
      </div>

      <p className="flex flex-wrap gap-2 text-sm">
        {/* 「기록된 사건」, not 「막힌 판단」: a withheld bar was never judged, so
            counting it as a blocked decision would overstate what happened. */}
        <Badge tone="neutral">
          기록된 사건 {runs.reduce((total, run) => total + run.count, 0)}봉
        </Badge>
        <Badge tone={withheld ? 'warn' : 'neutral'}>
          <Term name="W">보류</Term> {withheld == null ? '알 수 없음' : `${withheld}봉`}
        </Badge>
        <Badge tone={substituted ? 'warn' : 'neutral'}>
          <Term name="U">기록으로 대체</Term>{' '}
          {substituted == null ? '알 수 없음' : `${substituted}봉`}
        </Badge>
      </p>

      {runs.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          판단을 멈추거나 주문을 막은 기록이 없습니다.
        </p>
      ) : (
        <ol className="min-w-0 space-y-2">
          {shown.map((run, index) => (
            <li
              key={`${run.code}-${index}`}
              className="min-w-0 rounded-lg border border-slate-200 p-3 dark:border-slate-800"
            >
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="tabular-nums text-sm text-slate-500 dark:text-slate-400">
                  {run.firstTime ?? '--:--'}
                  {run.lastTime && run.lastTime !== run.firstTime ? ` – ${run.lastTime}` : ''}
                </span>
                <span className="font-medium">
                  <Term name={run.reason}>{glossaryLabel(run.reason)}</Term>
                </span>
                {run.step && (
                  <span className="text-sm text-slate-600 dark:text-slate-300">
                    단계: <Term name={run.step} />
                  </span>
                )}
                <Badge tone="neutral">{run.count}봉</Badge>
                <code className="text-xs text-slate-400 dark:text-slate-500">{run.code}</code>
              </div>
              {run.detail && (
                <p className="mt-2 text-xs text-slate-600 dark:text-slate-300">{run.detail}</p>
              )}
            </li>
          ))}
        </ol>
      )}
      {runs.length > shown.length && (
        <AsOf>
          기록 {runs.length}건 중 앞의 {shown.length}건만 보여 줍니다.
        </AsOf>
      )}
    </section>
  );
}
