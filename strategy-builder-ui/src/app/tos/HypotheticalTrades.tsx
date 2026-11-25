"use client";

import {
  excludedDecisionCount,
  hasHypotheticalPnl,
  hypotheticalError,
  type TosBarsDocument,
} from '@/lib/dashboard/tosBars';
import { glossaryLabel } from '@/lib/dashboard/tosGlossary';
import { PNL_CLASSES, PNL_WORDS, countLabel, pnlFigure, pointsLabel } from '@/lib/dashboard/tosMoney';
import { AttentionMark, Badge } from './marks';
import Term from './Term';

/**
 * What a session with no countable trade should say.
 *
 * «진입 없음» is a claim that the strategy never decided. It is only true when
 * nothing was left out either — a session whose decisions were all skipped or
 * unpriced DID decide, and saying it did not would hide exactly the thing the
 * operator came to see.
 */
export function emptyTradesPhrase(excluded: number): string {
  return excluded > 0 ? `셀 수 있는 거래 없음 (뺀 판단 ${excluded}건)` : '진입 없음';
}

/** A would-have-been figure. Outlined, never beside a realized one. */
function Money({ krw }: { krw: string | null | undefined }) {
  const figure = pnlFigure(krw);
  if (!figure) return <span className="text-slate-500 dark:text-slate-400">알 수 없음</span>;
  return (
    <span className={PNL_CLASSES[figure.direction]}>
      <span className="font-semibold tabular-nums">{figure.signed}원</span>{' '}
      <span className="text-xs">{PNL_WORDS[figure.direction]}</span>
    </span>
  );
}

/** `735.64` → `735.64`; an unparseable string is shown as itself. */
function points(value: string | null | undefined): string {
  if (value == null) return '알 수 없음';
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString('ko-KR', { maximumFractionDigits: 2 }) : value;
}

/**
 * «가상 거래» — what a decision-only tenant's judgements WOULD have earned.
 *
 * The futures trees decide and never order (operator decision 2026-11-05), so
 * there is no fill, no holding and no realized PnL for them anywhere on this
 * page. This table is the only way to read what the day's decisions amounted
 * to, and everything about it is built to stop that reading from drifting into
 * «we made 147,000원»:
 *
 * * every number carries the «체결 가정» label and the assumption list, and the
 *   three assumptions (a guaranteed fill at the decision bar's close, no fees,
 *   no slippage) all push the figure the same flattering way;
 * * the total states what it LEFT OUT — the skipped decisions, each with the
 *   document's own reason — rather than implying it counted everything;
 * * a session that decided nothing reads «진입 없음», never «0원».
 *
 * Nothing here is computed in the browser: `tools/tos_cp3/hypothetical_pnl.py`
 * produced every figure, and the page would have no business re-deriving a
 * money number from a chart.
 */
export default function HypotheticalTrades({ document }: { document: TosBarsDocument | null }) {
  if (!hasHypotheticalPnl(document)) {
    // No figure, but the exporter said why: show the reason rather than an
    // empty space that reads as «this tenant decided nothing».
    const error = hypotheticalError(document);
    if (!error) return null;
    return (
      <div
        role="group"
        aria-label="가상 거래"
        className="min-w-0 space-y-2 rounded-lg border border-dashed border-slate-400 p-3 dark:border-slate-500"
      >
        <h4 className="text-sm font-semibold">
          <Term name="hypothetical_pnl">가상 손익(체결 가정)</Term>
        </h4>
        <p className="text-sm">
          <AttentionMark>계산하지 못했습니다</AttentionMark>
        </p>
        <p className="text-xs text-slate-600 dark:text-slate-300">{error}</p>
      </div>
    );
  }
  const block = document?.hypothetical_pnl;
  const totals = block?.totals;
  const trades = block?.trades ?? [];
  const skipped = block?.skipped_decisions ?? [];
  const unpriced = block?.unpriced_decisions ?? [];
  const assumptions = block?.assumptions ?? [];
  const excluded = excludedDecisionCount(block);

  // Reasons, counted — «엔진 판단이 아님 1 · 시험 진입 3» says more than «4건».
  const byReason = new Map<string, number>();
  for (const row of skipped) {
    const reason = row.reason ?? '사유 없음';
    byReason.set(reason, (byReason.get(reason) ?? 0) + 1);
  }

  return (
    <div
      // `group`, not a landmark region: this sits INSIDE 「판단 근거」, and a
      // second region there would make the page's six sections read as seven.
      role="group"
      aria-label="가상 거래"
      className="min-w-0 space-y-3 rounded-lg border border-dashed border-slate-400 p-3 dark:border-slate-500"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h4 className="text-sm font-semibold">
          <Term name="hypothetical_pnl">가상 손익(체결 가정)</Term>
        </h4>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          실제 체결이 아닙니다. 이 tenant 는 주문을 내지 않으며, 아래 숫자는 실현 손익과 합산하지
          않습니다.
        </p>
      </div>

      <p className="flex flex-wrap items-center gap-1 text-xs">
        <span className="text-slate-500 dark:text-slate-400">
          <Term name="fill_assumption">체결 가정</Term>
        </span>
        {assumptions.length === 0 ? (
          <span className="text-slate-500 dark:text-slate-400">알 수 없음</span>
        ) : (
          assumptions.map((code) => (
            <Badge key={code} tone="neutral" title={code}>
              <Term name={code}>{glossaryLabel(code)}</Term>
            </Badge>
          ))
        )}
      </p>

      {trades.length === 0 ? (
        <p className="text-sm font-medium">
          {excluded > 0
            ? `${emptyTradesPhrase(excluded)} — 판단은 있었으나 아래 사유로 합계에서 뺐습니다.`
            : '진입 없음 — 이 세션은 진입 판단을 내지 않았습니다.'}
        </p>
      ) : (
        <div className="min-w-0 overflow-x-auto">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <caption className="sr-only">
              판단 봉 종가로 가정한 진입 · 청산과 그 손익
            </caption>
            <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
              <tr>
                <th scope="col" className="py-2 pr-3">진입</th>
                <th scope="col" className="py-2 pr-3">청산</th>
                <th scope="col" className="py-2 pr-3">포인트</th>
                <th scope="col" className="py-2 pr-3">가상 손익</th>
                <th scope="col" className="py-2">비고</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade, index) => (
                <tr
                  key={`${trade.entry_time_kst ?? index}`}
                  className="border-t border-slate-200 align-top dark:border-slate-800"
                >
                  <td className="py-2 pr-3">
                    <div className="tabular-nums font-medium">{trade.entry_time_kst ?? '시각 알 수 없음'}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {points(trade.entry_price_points)} · <Term name={trade.entry_rule_id} />
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    <div className="tabular-nums font-medium">{trade.exit_time_kst ?? '시각 알 수 없음'}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {points(trade.exit_price_points)} ·{' '}
                      {/* A forced close has no exit rule: the session ended. */}
                      {trade.exit_rule_id ? <Term name={trade.exit_rule_id} /> : '규칙 없음'}
                    </div>
                  </td>
                  <td className="py-2 pr-3 tabular-nums">{pointsLabel(trade.points)}</td>
                  <td className="py-2 pr-3">
                    <Money krw={trade.hypothetical_pnl_krw} />
                  </td>
                  <td className="py-2 text-xs">
                    {trade.forced_close === true ? (
                      <Badge tone="warn" title={trade.forced_close_reason ?? undefined}>
                        강제 청산
                      </Badge>
                    ) : (
                      <span className="text-slate-500 dark:text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="flex flex-wrap items-baseline gap-x-3 text-sm">
        <span className="text-slate-500 dark:text-slate-400">합계</span>
        {totals?.trades === 0 || totals?.hypothetical_pnl_krw == null ? (
          <span className="font-medium">{emptyTradesPhrase(excluded)}</span>
        ) : (
          <>
            <span className="tabular-nums font-medium">{pointsLabel(totals?.points)}</span>
            <Money krw={totals?.hypothetical_pnl_krw} />
          </>
        )}
        <span className="text-xs text-slate-500 dark:text-slate-400">
          <Term name="round_trip">왕복</Term> {countLabel(totals?.trades)} · 승{' '}
          {countLabel(totals?.wins, '')} · 강제 청산 {countLabel(totals?.forced_closes, '건')}
        </span>
      </p>

      {skipped.length > 0 && (
        <div className="text-xs">
          <p className="text-slate-600 dark:text-slate-300">
            합계에서 뺀 판단 {skipped.length}건 —{' '}
            {[...byReason.entries()]
              .map(([reason, count]) => `${glossaryLabel(reason)} ${count}`)
              .join(' · ')}
          </p>
          <ul className="mt-1 space-y-0.5">
            {skipped.map((row, index) => (
              <li key={`${row.time_kst ?? index}`} className="text-slate-500 dark:text-slate-400">
                {row.time_kst ?? '시각 알 수 없음'} · <Term name={row.rule_id} /> ·{' '}
                <Term name={row.reason}>{glossaryLabel(row.reason)}</Term>
              </li>
            ))}
          </ul>
        </div>
      )}

      {unpriced.length > 0 && (
        <p className="text-xs text-slate-600 dark:text-slate-300">
          가격을 읽지 못해 뺀 판단 {unpriced.length}건 —{' '}
          {unpriced.map((row) => row.time_kst ?? '시각 알 수 없음').join(' · ')}
        </p>
      )}

      {document?.hypothetical_pnl_error && (
        <p className="text-xs text-amber-700 dark:text-amber-300">
          가상 손익을 계산하지 못한 부분이 있습니다 · {document.hypothetical_pnl_error}
        </p>
      )}
    </div>
  );
}
