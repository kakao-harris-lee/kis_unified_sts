"use client";

import config from '@/config/tos-control-plane.json';
import type { TosBarsBar } from '@/lib/dashboard/tosBars';
import {
  probeTally,
  verdictTimeline,
  type BarVerdict,
  type TimelineEntry,
} from '@/lib/dashboard/tosDecision';
import { glossaryLabel } from '@/lib/dashboard/tosGlossary';
import { Badge, GateMark, type Tone } from './marks';
import Term from './Term';

interface VerdictTimelineProps {
  bars: TosBarsBar[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

const VERDICT_TONES: Record<BarVerdict['kind'], Tone> = {
  entry: 'good',
  exit: 'neutral',
  probe: 'warn',
  none: 'neutral',
  withheld: 'warn',
  unjoined: 'warn',
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

/**
 * «판단 타임라인» — the session as the handful of moments something changed.
 *
 * A 380-bar session is four to forty lines here: consecutive bars carrying the
 * same verdict, the same rule and the same gate collapse into one row with a
 * run length. Nothing is dropped — a run of 300 quiet bars is one line that
 * says 300 — and picking a row moves the chart and the checklist to the first
 * bar of that run.
 */
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

export default function VerdictTimeline({ bars, selectedIndex, onSelect }: VerdictTimelineProps) {
  const entries = verdictTimeline(bars);
  const shown = entries.slice(0, config.timelineMaxRows);
  // Opened at a glance, the rest one click away: a probe session alternates
  // «시험 진입» and «게이트 차단» for hundreds of bars, and forty rows of it
  // pushed the page past nine thousand pixels — the sections below became
  // unreachable by scrolling.
  const head = shown.slice(0, config.timelineHeadRows);
  const rest = shown.slice(config.timelineHeadRows);
  const probes = probeTally(bars);

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

  return (
    <div className="min-w-0 space-y-2">
      <h4 className="text-sm font-semibold">판단 타임라인</h4>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        판단이 바뀐 지점만 모았습니다. 줄을 고르면 그 봉으로 이동합니다.
      </p>
      {/* One line that answers the probe session before any row is read. */}
      {probes.fired > 0 && (
        <p className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm dark:border-slate-800">
          <Term name="R4-M2-PROBE-ENTRY-LONG" /> {probes.fired}봉 중 게이트 통과{' '}
          <span className="font-medium">{probes.passed}</span>
          {probes.gates.map((gate) => ` · ${gate.label} ${gate.count}`).join('')}
        </p>
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
      {entries.length > shown.length && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          바뀐 지점 {entries.length}개 중 앞의 {shown.length}개만 보여 줍니다.
        </p>
      )}
    </div>
  );
}
