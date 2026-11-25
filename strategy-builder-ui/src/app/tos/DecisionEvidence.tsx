"use client";

import type { TosBarsBar, TosBarsSummary } from '@/lib/dashboard/tosBars';
import {
  barVerdict,
  conditionRows,
  gateTally,
  ruleRoles,
  type ConditionRow,
} from '@/lib/dashboard/tosDecision';
import { glossaryLabel } from '@/lib/dashboard/tosGlossary';
import { Badge, GateMark, PassMark } from './marks';
import Term from './Term';

interface DecisionEvidenceProps {
  bar: TosBarsBar | null;
  summary: TosBarsSummary | null | undefined;
}

/** The formula, with each term marked by its truth on this bar. */
function Formula({ name, rows }: { name: string; rows: ConditionRow[] }) {
  return (
    <p className="flex flex-wrap items-center gap-x-1 gap-y-1 text-sm">
      <span className="font-medium">{name} =</span>
      {rows.map((row, position) => (
        <span key={row.index} className="inline-flex items-center gap-1">
          {position > 0 && <span className="text-slate-400">그리고</span>}
          <span
            className={
              row.passed === true
                ? 'rounded border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100'
                : row.passed === false
                  ? 'rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100'
                  : 'rounded border border-slate-300 px-1.5 py-0.5 text-slate-600 dark:border-slate-700 dark:text-slate-300'
            }
          >
            {row.passed === true ? '✓ ' : row.passed === false ? '— ' : '? '}
            {row.short}
          </span>
        </span>
      ))}
    </p>
  );
}

function ChecklistRow({ row }: { row: ConditionRow }) {
  return (
    <tr className="border-t border-slate-200 align-top dark:border-slate-800">
      <th scope="row" className="py-2 pr-3 text-left font-normal">
        <Term name={row.termKey}>{row.name}</Term>
        <span className="block text-xs text-slate-500 dark:text-slate-400">{row.expression}</span>
      </th>
      <td className="py-2 pr-3 tabular-nums">{row.actual}</td>
      <td className="py-2 pr-3 tabular-nums">{row.threshold ?? '예'}</td>
      <td className="py-2 pr-3">
        <PassMark passed={row.passed} />
      </td>
      <td className="py-2 text-xs text-slate-600 dark:text-slate-300">
        {row.distance
          ? `${row.distance.amount} ${row.distance.direction === 'down' ? '더 내려가야' : '더 올라가야'} 충족`
          : row.passed === false
            ? '값이 바뀌어야 충족'
            : ''}
      </td>
    </tr>
  );
}

/**
 * «왜 진입했나 / 안 했나» for ONE bar.
 *
 * Three layers, in the order an operator asks them:
 *
 * 1. the verdict — what this bar did, said outright, including the explicit
 *    non-trade case («신호 없음 — 미충족: …»), so a quiet bar is a stated
 *    answer rather than an empty space;
 * 2. the entry formula with every term marked, so a single blocking condition
 *    is visible without reading the table;
 * 3. the table, with the value this bar had, the threshold the document
 *    carries, and — where both sides are numbers — how far it was from passing.
 *
 * Below them, and visually separate, the kernel gates. A false condition and a
 * denied stage are different failures: one means the strategy saw nothing, the
 * other means it decided and was stopped. They never share a strip.
 */
export default function DecisionEvidence({ bar, summary }: DecisionEvidenceProps) {
  if (!bar) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">고른 봉이 없습니다.</p>;
  }

  const verdict = barVerdict(bar);
  const roles = ruleRoles(bar.rules);
  const entryRows = conditionRows(roles.entry);
  const firedExit = roles.exits.find((rule) => rule.fired === true) ?? null;
  const gates = gateTally(summary);

  return (
    <div className="min-w-0 space-y-4">
      <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-slate-500 dark:text-slate-400">
            {bar.time_kst ?? '시각 알 수 없음'}
          </span>
          <span className="text-lg font-semibold">{verdict.headline}</span>
          {verdict.ruleId && (
            <Badge tone="neutral" title={verdict.ruleId}>
              <Term name={verdict.ruleId} />
            </Badge>
          )}
          {verdict.gate && <GateMark label={verdict.gate.label} code={verdict.gate.reason} />}
        </div>
        <p className="mt-2 text-sm">
          {verdict.kind === 'none' ? (
            verdict.failing.length ? (
              <>진입 조건 중 {verdict.failing.join(' · ')} 이(가) 서지 않아 아무 것도 하지 않았습니다.</>
            ) : (
              <>어떤 규칙도 서지 않아 아무 것도 하지 않았습니다.</>
            )
          ) : verdict.kind === 'withheld' ? (
            <>이 봉은 평가하지 않았습니다. 조건이 거짓이었던 것이 아니라, 판단 자체를 하지 않았습니다.</>
          ) : verdict.kind === 'unjoined' ? (
            <>엔진 값을 찾지 못해 생산자 기록으로만 본 봉입니다. 통계의 분모에서 빠집니다.</>
          ) : verdict.blocked ? (
            <>규칙은 섰지만 커널 게이트에서 막혀 주문이 나가지 않았습니다.</>
          ) : (
            <>규칙이 서서 주문 경로로 넘어갔습니다.</>
          )}
        </p>
        {verdict.gate?.detail && (
          <p className="mt-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300">
            {verdict.gate.detail}
          </p>
        )}
        {firedExit && verdict.kind === 'exit' && (
          <p className="mt-2 text-xs text-slate-600 dark:text-slate-300">
            발화한 청산 규칙: <Term name={firedExit.rule_id} /> ({firedExit.rule_id})
          </p>
        )}
      </div>

      {entryRows.length > 0 ? (
        <div className="min-w-0 space-y-2">
          <Formula name={glossaryLabel(roles.entry?.rule_id)} rows={entryRows} />
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full min-w-[34rem] text-left text-sm">
              <caption className="sr-only">고른 봉의 진입 조건별 실제 값과 기준</caption>
              <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
                <tr>
                  <th scope="col" className="py-2 pr-3">조건</th>
                  <th scope="col" className="py-2 pr-3">이 봉의 값</th>
                  <th scope="col" className="py-2 pr-3">기준</th>
                  <th scope="col" className="py-2 pr-3">판정</th>
                  <th scope="col" className="py-2">충족까지</th>
                </tr>
              </thead>
              <tbody>
                {entryRows.map((row) => (
                  <ChecklistRow key={row.index} row={row} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          이 봉에는 평가된 진입 규칙이 없습니다.
        </p>
      )}

      <div className="min-w-0 space-y-2 rounded-lg border border-slate-200 p-3 dark:border-slate-800">
        <h4 className="text-sm font-semibold">커널 게이트</h4>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          전략 조건과는 별개입니다. 규칙이 서도 이 단계들이 막으면 주문은 나가지 않습니다.
        </p>
        <p className="text-sm">
          {verdict.gate ? (
            <GateMark label={verdict.gate.label} code={verdict.gate.reason} />
          ) : (
            <Badge tone="neutral">이 봉을 막은 게이트 없음</Badge>
          )}
        </p>
        {gates.length > 0 && (
          <>
            <p className="text-xs text-slate-500 dark:text-slate-400">이 세션 전체</p>
            <ul className="flex flex-wrap gap-2">
              {gates.map((gate) => (
                <li key={gate.code}>
                  <Badge tone="neutral" title={gate.code}>
                    {gate.label} <span className="font-medium">{gate.count}봉</span>
                  </Badge>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
