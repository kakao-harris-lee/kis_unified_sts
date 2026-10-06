"use client";

import { useEffect, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCcw } from 'lucide-react';
import { isAxiosError } from 'axios';
import config from '@/config/tos-control-plane.json';
import { isAcceptedProjection, projectionAge, projectionState, tosApi, type ProjectionState } from '@/lib/dashboard/tos';

const labels: Record<ProjectionState, string> = {
  loading: '상태를 불러오는 중', error: '상태 조회 연결 오류', missing: '아직 상태 파일이 없습니다',
  unreadable: '상태 파일을 열지 못했습니다', invalid: '상태 데이터 형식 오류', unsupported: '지원하지 않는 상태 버전',
  unknown: '상태 확인 불가', stale: '오래된 상태', recent: '최근 상태를 조회했습니다',
};

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
  return <section aria-label={title} className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
    <h2 className="mb-4 font-semibold">{title}</h2><dl className="space-y-3 text-sm">{children}</dl>
  </section>;
}
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="flex flex-wrap justify-between gap-2"><dt className="text-slate-500 dark:text-slate-400">{label}</dt><dd className="max-w-full break-words text-right">{children}</dd></div>;
}

export default function TosPage() {
  const query = useQuery({ queryKey: ['tos-operator-projection'], queryFn: tosApi.getProjection,
    refetchInterval: config.pollIntervalMs, retry: false });
  const [now, setNow] = useState(() => performance.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(performance.now()), config.clockTickMs);
    return () => window.clearInterval(timer);
  }, []);
  const response = query.data?.response;
  const age = projectionAge(response?.age_seconds, now - (query.data?.requestedAt ?? now));
  const state = projectionState(response, age, query.isError || query.fetchStatus === 'paused');
  // Same acceptance predicate the banner uses — see isAcceptedProjection.
  const p = response?.available && isAcceptedProjection(response.projection) ? response.projection : null;
  const httpStatus = isAxiosError(query.error) ? query.error.response?.status : undefined;
  const authError = httpStatus === 401 || httpStatus === 403;
  const warning = state !== 'recent' && state !== 'loading';

  return <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 text-slate-900 dark:text-slate-100">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-sm text-slate-500">TOS · 읽기 전용</p><h1 className="mt-1 text-2xl font-bold">TOS 운영 상태</h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">런타임이 마지막으로 내보낸 상태입니다. 조회 결과는 거래 실행 권한을 부여하지 않습니다.</p></div>
      <button type="button" onClick={() => void query.refetch()} disabled={query.isFetching}
        className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-slate-700">
        <RefreshCcw aria-hidden="true" className={`h-4 w-4 ${query.isFetching ? 'animate-spin' : ''}`} />새로고침
      </button>
    </div>
    <div role={warning ? 'alert' : 'status'} className={`rounded-xl border p-4 ${warning
      ? 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100'
      : 'border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900'}`}>
      <p className="font-semibold">{authError ? '조회 인증을 확인해 주세요' : labels[state]}</p>
      <p className="mt-1 text-sm">{authError ? 'API 키 또는 접근 권한을 확인한 후 다시 조회해 주세요.'
        : state === 'error' ? '연결을 확인한 후 다시 조회해 주세요. 남아 있는 값은 마지막 조회 기록입니다.'
        : state === 'stale' ? '새 상태가 도착하지 않았습니다. 아래 값으로 현재 런타임의 동작 여부를 판단하지 마세요.'
        : state === 'missing' ? '런타임의 상태 내보내기 경로와 조회 서비스 연결을 확인해 주세요.'
        : state === 'unreadable' ? '상태 파일의 경로와 접근 권한을 확인해 주세요. 파일 내용의 문제가 아닙니다.'
        : state === 'invalid' || state === 'unsupported' ? '런타임과 조회 서비스의 상태 형식을 확인해 주세요.'
        : '값이 없으면 알 수 없음으로 표시합니다. 최근 조회 여부와 시스템 정상 여부는 별개입니다.'}</p>
      <p className="mt-2 text-xs">내보낸 파일 경과: {age === null ? '알 수 없음' : `${Math.floor(age)}초`} · {config.staleAfterSeconds}초부터 오래된 상태로 표시 · {config.pollIntervalMs / 1000}초마다 조회</p>
    </div>
    {p && <>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-500">
        <span>런타임: {value(p.runtime?.cell_id)}</span><span>런타임 세대: {value(p.runtime?.runtime_generation)}</span><span>내보내기 세대: {p.projection_generation}</span>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card title="복구와 실행 상태">
          <Fact label="복구 판정">{value(p.recovery?.readiness_verdict)}</Fact>
          <Fact label="드라이버 연결">{flag(p.driver?.wired, '연결됨', '연결 안 됨')}</Fact>
          <Fact label="실행 중단">{flag(p.driver?.halt_latched, '중단됨', '중단 신호 없음')}</Fact>
          <Fact label="시간 신뢰 상태">{value(p.time?.health)}</Fact>
          <Fact label="복구 사유">{list(p.recovery?.reasons)}</Fact>
        </Card>
        <Card title="릴리스와 보호 상태">
          <Fact label="릴리스 수용">{flag(p.release?.admitted, '수용', '거부')}</Fact>
          <Fact label="배포 검증">{flag(p.release?.software_deployment_ok, '통과', '미통과')}</Fact>
          <Fact label="보호 분류">{value(p.protective?.last_verdict?.classification)}</Fact>
          <Fact label="해제 허용">{flag(p.protective?.last_verdict?.derestriction_admissible, '허용', '불허')}</Fact>
          <Fact label="용량 소진">{flag(p.protective?.last_verdict?.capacity_exhausted, '소진', '여유')}</Fact>
          <Fact label="보호 미확인 사유">{list(p.protective?.last_verdict?.reasons)}</Fact>
          <Fact label="보호 미평가 항목">{list(p.protective?.last_verdict?.unevaluated)}</Fact>
          <Fact label="의존성 수용">{flag(p.operations?.dependency_admission, '수용', '거부')}</Fact>
        </Card>
        <Card title="안전 서비스">
          {p.safety_mesh?.services && Object.keys(p.safety_mesh.services).length
            ? Object.entries(p.safety_mesh.services).map(([name, facts]) => <Fact key={name} label={name.toUpperCase()}>
              {flag(facts.clear, '해소', '미해소')}{facts.reasons?.length ? ` · ${facts.reasons.join(', ')}` : ''}
            </Fact>) : <Fact label="서비스 상태">알 수 없음</Fact>}
        </Card>
        <Card title="입력 유효성과 처리 대기">
          <Fact label="유효성 조립">{flag(p.currentness?.last_assemble_complete, '완료', '미완료')}</Fact>
          <Fact label="대기 항목">{list(p.currentness?.pending_dimensions)}</Fact>
          <Fact label="미처리 이벤트">{value(p.inbox?.unconsumed_count)}</Fact>
        </Card>
        <Card title="위험 원장과 증거">
          <Fact label="원장 마지막 순번">{value(p.rcl?.last_seq)}</Fact>
          <Fact label="열린 예약">{value(p.rcl?.open_reservations)}</Fact>
          <Fact label="증거 마지막 순번">{value(p.evidence?.tip_seq_excluding_stm_alert)}</Fact>
          <Fact label="증거 키 세대">{value(p.evidence?.key_generation)}</Fact>
        </Card>
        <Card title="백업과 알림">
          <Fact label="마지막 백업 세대">{value(p.operations?.last_backup?.generation)}</Fact>
          <Fact label="키 연속성">{value(p.operations?.key_continuity)}</Fact>
          <Fact label="미해결 알림 순번">{list(p.alerts?.unresolved_stm_alert_seqs)}</Fact>
          <Fact label="내보내기 오류 수">{value(p.export?.failures)}</Fact>
          {p.export?.last_error && <Fact label="내보내기 오류">오류가 기록되었습니다</Fact>}
        </Card>
      </div>
    </>}
  </div>;
}
