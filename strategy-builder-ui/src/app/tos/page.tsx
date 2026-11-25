"use client";

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCcw } from 'lucide-react';
import { isAxiosError } from 'axios';
import config from '@/config/tos-control-plane.json';
import {
  isAcceptedProjection,
  projectionAge,
  projectionState,
  tosApi,
  type ProjectionState,
} from '@/lib/dashboard/tos';
import { LATEST_SESSION } from '@/lib/dashboard/tosBars';
import BarsPanel from './BarsPanel';
import EventLog from './EventLog';
import SessionPicker from './SessionPicker';
import StatusStrip from './StatusStrip';
import SymbolsPanel from './SymbolsPanel';
import SystemInternals from './SystemInternals';
import TenantCards from './TenantCards';
import { PROJECTION_KEY, useBarsDocument, useSessionsList, useSymbolsDocument } from './queries';

const labels: Record<ProjectionState, string> = {
  loading: '상태를 불러오는 중',
  error: '상태 조회 연결 오류',
  missing: '아직 상태 파일이 없습니다',
  unreadable: '상태 파일을 열지 못했습니다',
  invalid: '상태 데이터 형식 오류',
  unsupported: '지원하지 않는 상태 버전',
  unknown: '상태 확인 불가',
  stale: '오래된 상태',
  recent: '최근 상태를 조회했습니다',
};

/**
 * The /tos operator page.
 *
 * It answers four questions, top to bottom, and each section says which one it
 * answers in plain Korean: «지금 괜찮은가» → «tenant 별로 어디까지 왔나» →
 * «왜 진입했나 / 안 했나» → «무엇을 사고팔았나» → «무슨 일이 있었나». What used
 * to be the whole page — the paper cell's own projection cards — is last and
 * collapsed, because it describes the machinery rather than the trading, and
 * because it describes ONE resident paper cell rather than the tenant sessions
 * an operator comes here to read.
 *
 * This component owns two things and no more: which session the lower sections
 * describe, and the per-session bars read they all share. Everything else is a
 * presentational component with its document passed in, so each can be
 * asserted on its own.
 *
 * Read-only throughout. The only element that acts is 새로고침, which re-reads
 * the same documents; selecting a tenant or a bar changes what is displayed and
 * nothing else. No control here can start, stop or order anything.
 */
export default function TosPage() {
  const query = useQuery({
    queryKey: PROJECTION_KEY,
    queryFn: tosApi.getProjection,
    refetchInterval: config.pollIntervalMs,
    retry: false,
  });
  const [now, setNow] = useState(() => performance.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(performance.now()), config.clockTickMs);
    return () => window.clearInterval(timer);
  }, []);

  const response = query.data?.response;
  const age = projectionAge(response?.age_seconds, now - (query.data?.requestedAt ?? now));
  const state = projectionState(response, age, query.isError || query.fetchStatus === 'paused');
  // Same acceptance predicate the banner uses — see isAcceptedProjection.
  const projection =
    response?.available && isAcceptedProjection(response.projection) ? response.projection : null;
  const httpStatus = isAxiosError(query.error) ? query.error.response?.status : undefined;
  const authError = httpStatus === 401 || httpStatus === 403;
  const warning = state !== 'recent' && state !== 'loading';

  // The session the four lower sections describe. It opens on the sentinel so
  // the first paint needs no listing round trip and survives a listing that
  // fails; picking a tenant card or the dropdown replaces it.
  const [session, setSession] = useState(LATEST_SESSION);
  const sessions = useSessionsList();
  const symbols = useSymbolsDocument();
  const bars = useBarsDocument(session);
  // Which card is highlighted: the id the route RESOLVED, so `latest` marks the
  // tenant actually on screen instead of leaving every card unselected.
  const active = bars.response?.session ?? session;

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 text-slate-900 dark:text-slate-100">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">TOS · 읽기 전용</p>
          <h1 className="mt-1 text-2xl font-bold">TOS 운영 상태</h1>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            런타임이 마지막으로 내보낸 기록입니다. 조회 결과는 거래 실행 권한을 부여하지 않습니다.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void query.refetch()}
          disabled={query.isFetching}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-slate-700"
        >
          <RefreshCcw aria-hidden="true" className={`h-4 w-4 ${query.isFetching ? 'animate-spin' : ''}`} />
          새로고침
        </button>
      </div>

      <div
        role={warning ? 'alert' : 'status'}
        className={`rounded-xl border p-4 ${
          warning
            ? 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100'
            : 'border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900'
        }`}
      >
        <p className="font-semibold">{authError ? '조회 인증을 확인해 주세요' : labels[state]}</p>
        <p className="mt-1 text-sm">
          {authError
            ? 'API 키 또는 접근 권한을 확인한 후 다시 조회해 주세요.'
            : state === 'error'
              ? '연결을 확인한 후 다시 조회해 주세요. 남아 있는 값은 마지막 조회 기록입니다.'
              : state === 'stale'
                ? '새 상태가 도착하지 않았습니다. 아래 값으로 현재 런타임의 동작 여부를 판단하지 마세요.'
                : state === 'missing'
                  ? '런타임의 상태 내보내기 경로와 조회 서비스 연결을 확인해 주세요.'
                  : state === 'unreadable'
                    ? '상태 파일의 경로와 접근 권한을 확인해 주세요. 파일 내용의 문제가 아닙니다.'
                    : state === 'invalid' || state === 'unsupported'
                      ? '런타임과 조회 서비스의 상태 형식을 확인해 주세요.'
                      : '값이 없으면 알 수 없음으로 표시합니다. 최근 조회 여부와 시스템 정상 여부는 별개입니다.'}
        </p>
        <p className="mt-2 text-xs">
          paper 셀 상태 경과: {age === null ? '알 수 없음' : `${Math.floor(age)}초`} ·{' '}
          {config.staleAfterSeconds}초부터 오래된 상태로 표시 · {config.pollIntervalMs / 1000}초마다
          조회
        </p>
      </div>

      <StatusStrip
        projectionState={state}
        projection={projection}
        projectionAgeSeconds={age}
        symbols={symbols}
      />

      <TenantCards sessions={sessions} symbols={symbols} selected={active} onSelect={setSession} />
      <SessionPicker sessions={sessions} value={session} onChange={setSession} />

      {/* Three views of ONE session: the evidence a decision rests on, what was
          traded, and what stopped. They share the page's bars read, so a
          megabyte is fetched once rather than once per section. */}
      <BarsPanel key={active} requested={session} read={bars} />
      <SymbolsPanel read={symbols} />
      <EventLog bars={bars.document?.bars ?? []} summary={bars.document?.summary} />

      <SystemInternals
        projection={projection}
        summary={bars.document?.summary}
        bars={bars.document?.bars ?? []}
        sessionLabel={bars.document?.session ?? session}
      />
    </div>
  );
}
