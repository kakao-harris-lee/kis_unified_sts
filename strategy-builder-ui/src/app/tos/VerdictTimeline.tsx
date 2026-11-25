"use client";

import { useState } from 'react';
import config from '@/config/tos-control-plane.json';
import type { TosBarsBar } from '@/lib/dashboard/tosBars';
import {
  isProbeRule,
  isSignalVerdict,
  planTimeline,
  timelineSummary,
  verdictTimeline,
  type BarVerdict,
  type SignalCount,
  type ProbePredicate,
  type TimelineEntry,
  type VerdictKind,
} from '@/lib/dashboard/tosDecision';
import { glossaryLabel } from '@/lib/dashboard/tosGlossary';
import { Badge, GateMark, type Tone } from './marks';
import Term from './Term';

interface VerdictTimelineProps {
  bars: TosBarsBar[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  /** The document's probe test, so «시험 진입» is the document's word. */
  isProbe?: ProbePredicate;
}

const VERDICT_TONES: Record<BarVerdict['kind'], Tone> = {
  entry: 'good',
  exit: 'neutral',
  probe: 'warn',
  none: 'neutral',
  withheld: 'warn',
  unjoined: 'warn',
};

const OMITTED_LABELS: Record<VerdictKind, string> = {
  entry: '진입',
  exit: '청산',
  probe: '시험 진입',
  none: '신호 없음',
  withheld: '평가 보류',
  unjoined: '대조 불가',
};

/** The sentence a row says, including the explicit non-trade case. */
function sentence(verdict: BarVerdict): string {
  if (verdict.kind === 'none') {
    return verdict.failing.length
      ? `신호 없음 — 미충족: ${verdict.failing.join(', ')}`
      : '신호 없음';
  }
  if (verdict.kind === 'withheld') return '평가 보류 — 이 봉은 판단하지 않았습니다';
  if (verdict.kind === 'unjoined') return '대조 불가 — 엔진 값을 찾지 못했습니다';
  const rule = verdict.ruleId ? glossaryLabel(verdict.ruleId) : '규칙 알 수 없음';
  return verdict.blocked
    ? `${verdict.headline} 신호 — 게이트에서 차단 (${rule})`
    : `${verdict.headline} — ${rule}`;
}

/** «진입 신호 6봉 (게이트 통과 1)», or nothing when the kind never fired. */
function countPhrase(label: string, count: SignalCount): string | null {
  if (count.bars === 0) return null;
  return `${label} ${count.bars}봉 (게이트 통과 ${count.passed})`;
}

function Row({
  entry,
  selected,
  onSelect,
}: {
  entry: TimelineEntry;
  selected: boolean;
  onSelect: (index: number) => void;
}) {
  return (
    <li className="min-w-0">
      <label
        className={`flex min-w-0 cursor-pointer flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border px-2 py-1.5 text-sm ${
          selected
            ? 'border-slate-900 bg-slate-50 dark:border-slate-200 dark:bg-slate-800'
            : 'border-transparent hover:border-slate-300 dark:hover:border-slate-700'
        }`}
      >
        <input
          type="radio"
          name="tos-timeline"
          value={entry.index}
          checked={selected}
          onChange={() => onSelect(entry.index)}
          className="sr-only"
        />
        <span className="w-12 shrink-0 tabular-nums text-slate-500 dark:text-slate-400">
          {entry.timeKst ?? '--:--'}
        </span>
        <Badge tone={VERDICT_TONES[entry.verdict.kind]}>{entry.verdict.headline}</Badge>
        <span className="min-w-0 flex-1 break-words">{sentence(entry.verdict)}</span>
        {entry.verdict.gate && (
          <GateMark label={entry.verdict.gate.label} code={entry.verdict.gate.reason} />
        )}
        {entry.run > 1 && (
          <span className="text-xs text-slate-500 dark:text-slate-400">{entry.run}봉 연속</span>
        )}
        {entry.verdict.ruleId && (
          <span className="text-xs text-slate-400 dark:text-slate-500">
            <Term name={entry.verdict.ruleId}>{entry.verdict.ruleId}</Term>
          </span>
        )}
      </label>
    </li>
  );
}

/**
 * «판단 타임라인» — the session as the handful of moments something changed.
 *
 * Consecutive bars carrying the same verdict, the same rule, the same gate and
 * the same failing conditions collapse into one row with a run length.
 *
 * **A row that records a trade is never dropped and never hidden without a
 * count.** An earlier revision capped the list at forty rows, which on
 * `stock-005380-r1-20261125` fell between the quiet morning and the day's
 * actual entry at 11:18: 거래 현황 showed the fill and this panel refused to
 * show the decision behind it, even under «더 보기». So the cap now applies to
 * the quiet background only, what it drops is named by kind, and a filter
 * lists every entry, exit and probe with no cap at all.
 */
export default function VerdictTimeline({
  bars,
  selectedIndex,
  onSelect,
  isProbe = isProbeRule,
}: VerdictTimelineProps) {
  const [tradesOnly, setTradesOnly] = useState(false);
  const entries = verdictTimeline(bars, isProbe);
  const summary = timelineSummary(entries);
  const signals = entries.filter((entry) => isSignalVerdict(entry.verdict.kind));
  const plan = planTimeline(entries, config.timelineQuietMaxRows);
  const list = tradesOnly ? signals : plan.shown;
  const head = tradesOnly ? list : list.slice(0, config.timelineHeadRows);
  const rest = tradesOnly ? [] : list.slice(config.timelineHeadRows);

  if (!entries.length) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">판단 기록이 없습니다.</p>;
  }

  const row = (entry: TimelineEntry) => (
    <Row
      key={entry.index}
      entry={entry}
      selected={entry.index === selectedIndex}
      onSelect={onSelect}
    />
  );

  const counts = [
    countPhrase('진입 신호', summary.entry),
    countPhrase('청산 신호', summary.exit),
    countPhrase('시험 진입', summary.probe),
    summary.quietRuns ? `신호 없음 ${summary.quietRuns}구간` : null,
    summary.withheldRuns ? `평가 보류 ${summary.withheldRuns}구간` : null,
    summary.unjoinedRuns ? `대조 불가 ${summary.unjoinedRuns}구간` : null,
  ].filter((part): part is string => part !== null);

  return (
    <div className="min-w-0 space-y-2">
      <h4 className="text-sm font-semibold">판단 타임라인</h4>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        판단이 바뀐 지점만 모았습니다. 줄을 고르면 그 봉으로 이동합니다.
      </p>

      {/* The whole session in one line, for every tenant — not only probe ones. */}
      <p className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm dark:border-slate-800">
        {counts.length ? counts.join(' · ') : '판단이 바뀐 지점이 없습니다'}
      </p>

      {signals.length > 0 && (
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={tradesOnly}
            onChange={(event) => setTradesOnly(event.target.checked)}
          />
          <span>진입 · 청산만 보기 ({signals.length}줄)</span>
        </label>
      )}

      <ul role="radiogroup" aria-label="판단이 바뀐 지점" className="min-w-0 space-y-1">
        {head.map(row)}
      </ul>
      {rest.length > 0 && (
        <details className="min-w-0">
          <summary className="cursor-pointer text-xs text-slate-500 dark:text-slate-400">
            {rest.length}줄 더 보기
          </summary>
          <ul aria-label="나머지 판단 지점" className="mt-1 min-w-0 space-y-1">
            {rest.map(row)}
          </ul>
        </details>
      )}
      {!tradesOnly && plan.omitted.length > 0 && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {plan.omitted
            .map((omitted) => `${OMITTED_LABELS[omitted.kind]} ${omitted.count}구간`)
            .join(' · ')}
          은 접었습니다. 진입 · 청산 · 시험 진입은 모두 위에 있습니다.
        </p>
      )}
    </div>
  );
}
