"use client";

import config from '@/config/tos-control-plane.json';
import type { ProjectionState, TosProjection } from '@/lib/dashboard/tos';
import { isTodaysDocument, sessionPhase } from '@/lib/dashboard/tosSymbols';
import { AlertTriangle } from 'lucide-react';
import { AsOf, Badge, ageLabel, type Tone } from './marks';
import Term from './Term';
import type { SymbolsRead } from './queries';

interface StatusStripProps {
  projectionState: ProjectionState;
  projection: TosProjection | null;
  projectionAgeSeconds: number | null;
  symbols: SymbolsRead;
  /**
   * The page's own wording for a projection state that is not «recent».
   *
   * It used to head a full-width banner; now that a stale paper cell no longer
   * earns one, the specific sentence («아직 상태 파일이 없습니다», …) lands here
   * so the operator still sees WHICH kind of absence it is.
   */
  stateLabel: string;
}

interface Fact {
  key: string;
  label: string;
  value: string;
  tone: Tone;
  /** Carries the warning icon, so the one real alarm is not a hue alone. */
  alert?: boolean;
}

/**
 * «지금 괜찮은가» — the one line above everything else.
 *
 * It is assembled from the three documents this page already reads, and from
 * nothing else. Two consequences are deliberate:
 *
 * * the runtime fact is labelled «paper 셀» wherever it appears, because
 *   `/api/tos/projection` describes the ONE resident paper cell and says
 *   nothing about the CP-3 tenant sessions whose cards sit below it. The page
 *   used to show those five cards unlabelled, which read as «the system», and
 *   that is the single misreading this strip exists to stop;
 * * «막힌 판단» is a count with a neutral tone, not an alarm. On a normal day
 *   every tenant records STAGE_DENIED on its exits — there is no position to
 *   close in a decision-only tree — so colouring it red would make an ordinary
 *   session look like an incident every single day.
 *
 * A status board that judges the whole system does not exist yet, so this
 * strip does not pretend to be one: it reports what each document says and
 * leaves the verdict to the operator.
 */
export default function StatusStrip({
  projectionState,
  projection,
  projectionAgeSeconds,
  symbols,
  stateLabel,
}: StatusStripProps) {
  const facts: Fact[] = [];

  // 1. The resident paper cell, from the polled projection.
  //
  // A latched halt shares amber with a stale read rather than taking a red of
  // its own: red belongs to price on this page. What separates them is the
  // warning icon and the words 「실행 중단」, which say more than a hue could.
  const halted = projection?.driver?.halt_latched;
  const projectionTone: Tone =
    halted === true
      ? 'warn'
      : projectionState === 'recent'
        ? 'good'
        : projectionState === 'loading'
          ? 'neutral'
          : 'warn';
  facts.push({
    key: 'paper',
    label: 'paper 셀',
    alert: halted === true,
    value:
      halted === true
        ? `실행 중단${projection?.driver?.halt_reason ? ` · ${projection.driver.halt_reason}` : ''}`
        : projectionState === 'recent'
          ? '최근 상태 도착'
          : projectionState === 'stale'
            ? `${config.staleAfterSeconds}초 넘게 새 상태 없음`
            : projectionState === 'loading'
              ? '불러오는 중'
              : stateLabel,
    tone: projectionTone,
  });

  // 2. Whether the per-symbol document describes today at all.
  const today = isTodaysDocument(symbols.document);
  facts.push({
    key: 'day',
    label: '종목 기록 기준일',
    value:
      symbols.document?.date == null
        ? '알 수 없음'
        : today === false
          ? `${symbols.document.date} · 오늘 아님`
          : symbols.document.date,
    tone: symbols.document?.date == null ? 'warn' : today === false ? 'warn' : 'good',
  });

  // 3. The tenant sessions, by phase. A status outside RUNNING/ENDED is what
  //    an operator has to look at; the rest is routine.
  const rows = symbols.document?.symbols ?? [];
  if (rows.length) {
    const phases = rows.map((row) => sessionPhase(row.session));
    const unknown = phases.filter((phase) => phase === 'unknown').length;
    const running = phases.filter((phase) => phase === 'running').length;
    const settled = phases.filter((phase) => phase === 'settled').length;
    const none = phases.filter((phase) => phase === 'none').length;
    const parts = [
      running ? `진행 중 ${running}` : null,
      settled ? `종료 ${settled}` : null,
      none ? `시작 안 함 ${none}` : null,
      unknown ? `확인 필요 ${unknown}` : null,
    ].filter((part): part is string => part !== null);
    facts.push({
      key: 'sessions',
      label: `종목 tenant ${rows.length}개`,
      value: parts.join(' · ') || '알 수 없음',
      tone: unknown || none ? 'warn' : 'good',
    });

    // 4. How many decisions a kernel gate stopped today, across all tenants.
    //    `flow_counts` is null when the exporter had no source for it, which is
    //    not the same fact as zero.
    const counted = rows
      .map((row) => row.halt?.flow_counts)
      .filter((counts): counts is Record<string, number> => counts != null)
      .map((counts) => Object.values(counts).reduce((total, n) => total + n, 0));
    facts.push({
      key: 'gates',
      label: '게이트가 막은 판단',
      value: counted.length === 0 ? '알 수 없음' : `${counted.reduce((a, b) => a + b, 0)}건`,
      tone: 'neutral',
    });
  }

  return (
    <section
      aria-label="지금 상태"
      className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="font-semibold">지금 괜찮은가</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          아래 세 기록이 말하는 것만 모았습니다. 주문을 내리거나 멈출 수 있는 화면이 아닙니다.
        </p>
      </div>
      <ul className="mt-3 flex flex-wrap gap-2">
        {facts.map((fact) => (
          <li key={fact.key}>
            <Badge tone={fact.tone}>
              {fact.alert && <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />}
              <span className="text-slate-500 dark:text-slate-400">{fact.label}</span>
              <span className="font-medium">{fact.value}</span>
            </Badge>
          </li>
        ))}
      </ul>
      <AsOf>
        <span className="mr-3">
          <Term name="paper_cell" /> 상태: {ageLabel(projectionAgeSeconds)} ·{' '}
          {config.pollIntervalMs / 1000}초마다 조회
        </span>
        <span>
          종목 기록: {symbols.document?.generated_kst ?? '내보낸 시각 알 수 없음'}
          {symbols.response?.age_seconds != null ? ` · ${ageLabel(symbols.response.age_seconds)}` : ''}
        </span>
      </AsOf>
    </section>
  );
}
