"use client";

import type { ReactNode } from 'react';
import type { TosProjection } from '@/lib/dashboard/tos';
import type { TosBarsBar, TosBarsSummary } from '@/lib/dashboard/tosBars';
import BarsRuleBands from './BarsRuleBands';
import BarsSummaryTable from './BarsSummaryTable';
import Term from './Term';

function value(v: string | number | null | undefined): string {
  return v == null ? '알 수 없음' : String(v);
}
function flag(v: boolean | null | undefined, yes: string, no: string): string {
  return v == null ? '알 수 없음' : v ? yes : no;
}
function list(v: (string | number)[] | null | undefined): string {
  return v == null ? '알 수 없음' : v.length ? v.join(', ') : '없음';
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section
      aria-label={title}
      className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <h3 className="mb-4 font-semibold">{title}</h3>
      <dl className="space-y-3 text-sm">{children}</dl>
    </section>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-2">
      <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="max-w-full break-words text-right">{children}</dd>
    </div>
  );
}

interface SystemInternalsProps {
  projection: TosProjection | null;
  /** The verification summary of the session the sections above describe. */
  summary: TosBarsSummary | null | undefined;
  bars: TosBarsBar[];
  sessionLabel: string;
}

/**
 * «시스템 내부» — the two surfaces that describe the machinery, not the trading.
 *
 * Collapsed by default and kept whole. The five projection cards and the
 * verification summary were the entire page before this change, and they are
 * still the right answer to «런타임이 스스로를 어떻게 보고하나» — but they are
 * not what an operator opens the page to ask, and leaving them above the
 * trading view is what made the page unreadable.
 *
 * The heading says WHICH THING each half describes, because that is the fact
 * the old layout omitted: the projection is the ONE resident paper cell, not
 * the CP-3 tenant sessions above; the summary is the exporter's own
 * view-versus-journal verification of one session, not a trading result.
 */
export default function SystemInternals({
  projection,
  summary,
  bars,
  sessionLabel,
}: SystemInternalsProps) {
  return (
    <details className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <summary className="cursor-pointer font-semibold">
        시스템 내부
        <span className="ml-2 text-sm font-normal text-slate-500 dark:text-slate-400">
          paper 셀 상태와 기록 검증 — 평소에는 볼 필요가 없습니다
        </span>
      </summary>

      <div className="mt-4 min-w-0 space-y-5">
        <div className="min-w-0 space-y-3">
          <h3 className="text-sm font-semibold">
            <Term name="paper_cell" /> 상태
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            상주 paper 셀이 스스로 내보낸 값입니다. 위의 tenant 세션을 설명하지 않습니다.
          </p>
          {projection ? (
            <>
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-500">
                <span>런타임: {value(projection.runtime?.cell_id)}</span>
                <span>런타임 세대: {value(projection.runtime?.runtime_generation)}</span>
                <span>내보내기 세대: {projection.projection_generation}</span>
              </div>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <Card title="복구와 실행 상태">
                  <Fact label="복구 판정">{value(projection.recovery?.readiness_verdict)}</Fact>
                  <Fact label="드라이버 연결">{flag(projection.driver?.wired, '연결됨', '연결 안 됨')}</Fact>
                  <Fact label="실행 중단">{flag(projection.driver?.halt_latched, '중단됨', '중단 신호 없음')}</Fact>
                  <Fact label="시간 신뢰 상태">{value(projection.time?.health)}</Fact>
                  <Fact label="복구 사유">{list(projection.recovery?.reasons)}</Fact>
                </Card>
                <Card title="릴리스 상태">
                  <Fact label="릴리스 수용">{flag(projection.release?.admitted, '수용', '거부')}</Fact>
                  <Fact label="배포 검증">{flag(projection.release?.software_deployment_ok, '통과', '미통과')}</Fact>
                  <Fact label="의존성 수용">{flag(projection.operations?.dependency_admission, '수용', '거부')}</Fact>
                </Card>
                <Card title="입력 유효성과 처리 대기">
                  <Fact label="유효성 조립">{flag(projection.currentness?.last_assemble_complete, '완료', '미완료')}</Fact>
                  <Fact label="대기 항목">{list(projection.currentness?.pending_dimensions)}</Fact>
                  <Fact label="미처리 이벤트">{value(projection.inbox?.unconsumed_count)}</Fact>
                </Card>
                <Card title="위험 원장과 증거">
                  <Fact label="원장 마지막 순번">{value(projection.rcl?.last_seq)}</Fact>
                  <Fact label="열린 예약">{value(projection.rcl?.open_reservations)}</Fact>
                  <Fact label="증거 마지막 순번">{value(projection.evidence?.tip_seq_excluding_stm_alert)}</Fact>
                  <Fact label="증거 키 세대">{value(projection.evidence?.key_generation)}</Fact>
                </Card>
                <Card title="백업과 알림">
                  <Fact label="마지막 백업 세대">{value(projection.operations?.last_backup?.generation)}</Fact>
                  <Fact label="키 연속성">{value(projection.operations?.key_continuity)}</Fact>
                  <Fact label="미해결 알림 순번">{list(projection.alerts?.unresolved_stm_alert_seqs)}</Fact>
                  <Fact label="내보내기 오류 수">{value(projection.export?.failures)}</Fact>
                  {projection.export?.last_error && <Fact label="내보내기 오류">오류가 기록되었습니다</Fact>}
                </Card>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              읽을 수 있는 paper 셀 상태가 없습니다.
            </p>
          )}
        </div>

        <div className="min-w-0 space-y-3">
          <h3 className="text-sm font-semibold">기록 검증 · {sessionLabel}</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            엔진이 본 값과 생산자가 남긴 기록이 어긋나지 않았는지에 대한 내보내기 도구의 자체 점검입니다.
            거래 성과가 아닙니다.
          </p>
          {summary ? (
            <>
              <BarsRuleBands bars={bars} rules={summary.rules ?? []} />
              <BarsSummaryTable summary={summary} />
            </>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              이 세션의 검증 요약이 없습니다.
            </p>
          )}
        </div>
      </div>
    </details>
  );
}
