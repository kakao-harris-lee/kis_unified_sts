"use client";

import type { TosBarsSummary } from '@/lib/dashboard/tosBars';

interface BarsSummaryTableProps {
  summary: TosBarsSummary;
}

function count(value: number | null | undefined): string {
  return value == null ? '알 수 없음' : String(value);
}

function pct(value: number | null | undefined): string {
  return value == null ? '알 수 없음' : `${value.toFixed(1)}%`;
}

function tally(values: Record<string, number> | null | undefined): string {
  if (values == null) return '알 수 없음';
  const entries = Object.entries(values);
  return entries.length ? entries.map(([key, n]) => `${key} ${n}`).join(' · ') : '없음';
}

/**
 * Which comparison blocked which rule, how often — the roadmap §P1 question.
 *
 * The denominator is the COUNTED bars, not every rendered bar: a withheld bar
 * was never judged and a journal-substituted bar was judged on stand-in inputs,
 * so neither can carry a claim about what blocked a rule. The populations line
 * states all three so the exclusions are visible rather than merely absent.
 */
export default function BarsSummaryTable({ summary }: BarsSummaryTableProps) {
  return (
    <div className="min-w-0 space-y-3">
      <p className="text-sm text-slate-600 dark:text-slate-300">
        전체 {count(summary.bars)}봉 · 분모 {count(summary.counted_bars)}봉(엔진 값 기준)
        {' · '}보류 {count(summary.withheld_bars)}봉 · journal 대체 {count(summary.substituted_bars)}봉
      </p>
      <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500 dark:text-slate-400">엔진 값 ≠ journal</dt>
          <dd className="text-right">
            {count(summary.view_diff_bars)}봉 · {tally(summary.view_diff_fields)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500 dark:text-slate-400">결정 ≠ 엔진 결과</dt>
          <dd className="text-right">
            {count(summary.disagreement_bars)}봉 · 비교 불가 {count(summary.not_comparable_bars)}봉
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500 dark:text-slate-400">결정</dt>
          <dd className="text-right">{tally(summary.decisions)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500 dark:text-slate-400">증거 결과</dt>
          <dd className="text-right">{tally(summary.evidence_outcomes)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500 dark:text-slate-400">증거 정지</dt>
          <dd className="text-right">{tally(summary.evidence_halts)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500 dark:text-slate-400">조인 실패</dt>
          <dd className="text-right">{tally(summary.unjoined)}</dd>
        </div>
      </dl>
      <div className="min-w-0 overflow-x-auto">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <caption className="sr-only">규칙별·비교식별 거짓 비율</caption>
          <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
              <th scope="col" className="py-2 pr-3">규칙 / 비교식</th>
              <th scope="col" className="py-2 pr-3 text-right">발화 / 거짓</th>
              <th scope="col" className="py-2 pr-3 text-right">분모</th>
              <th scope="col" className="py-2 text-right">비율</th>
            </tr>
          </thead>
          <tbody>
            {(summary.rules ?? []).map((rule, ruleIndex) => [
              <tr
                key={`rule-${ruleIndex}`}
                className="border-t border-slate-200 font-medium dark:border-slate-800"
              >
                <th scope="row" className="py-2 pr-3 text-left font-medium">
                  {rule.label ?? '?'} · {rule.rule_id ?? '알 수 없음'}
                </th>
                <td className="py-2 pr-3 text-right">{count(rule.fired_bars)} 발화</td>
                <td className="py-2 pr-3 text-right">{count(rule.bars)}</td>
                <td className="py-2 text-right">{pct(rule.fired_pct)}</td>
              </tr>,
              ...(rule.compares ?? []).map((compare, compareIndex) => (
                <tr
                  key={`rule-${ruleIndex}-compare-${compareIndex}`}
                  className="border-t border-slate-100 dark:border-slate-800/60"
                >
                  <td className="py-1.5 pr-3 pl-4 text-slate-600 dark:text-slate-300">
                    {compare.index ?? compareIndex + 1} {compare.expression ?? '알 수 없음'}
                  </td>
                  <td className="py-1.5 pr-3 text-right">{count(compare.failed_bars)} 거짓</td>
                  <td className="py-1.5 pr-3 text-right">{count(compare.bars)}</td>
                  <td className="py-1.5 text-right">{pct(compare.failed_pct)}</td>
                </tr>
              )),
            ])}
          </tbody>
        </table>
      </div>
    </div>
  );
}
