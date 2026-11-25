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
import {
  PROJECTION_KEY,
  isLiveSession,
  useBarsDocument,
  useSessionsList,
  useStatusDocument,
  useSymbolsDocument,
} from './queries';

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
  // A full-width alert above everything is for a request that did not land:
  // a connection failure or a rejected key, which makes the WHOLE page
  // untrustworthy. A stale or absent projection document is neither — the
  // paper cell stops writing when it stops at 15:45, so an amber banner would
  // dominate the page every single evening while the tenant sections below it
  // are perfectly current. That fact belongs to the paper cell, and the status
  // strip and 시스템 내부 are where the page says so.
  const fetchFailed = authError || state === 'error';

  // The session the four lower sections describe. It opens on the sentinel so
  // the first paint needs no listing round trip and survives a listing that
  // fails; picking a tenant card or the dropdown replaces it.
  const [session, setSession] = useState(LATEST_SESSION);
  const sessions = useSessionsList();
  const status = useStatusDocument();
  const symbols = useSymbolsDocument();
  // A session still running gets its document re-read on the intraday cadence
  // (plan §P3); a finished one is read once. Deciding here keeps the panel
  // presentational and keeps the cost to the one session on screen.
  //
  // The `latest` sentinel is resolved by the ROUTE, which this decision cannot
  // wait for without making the read depend on its own result. It uses the
  // listing's newest entry instead — the same ordering the route resolves
  // `latest` by. A disagreement would only start or skip polling on one
  // session; nothing rendered depends on it.
  const resolvedName =
    session === LATEST_SESSION ? (sessions.sessions[0]?.session ?? null) : session;
  const selectedEntry =
    sessions.sessions.find((entry) => entry.session === resolvedName) ?? null;
  const selectedRow =
    symbols.document?.symbols?.find((row) => row.session?.name === resolvedName) ?? null;
  const live = isLiveSession(selectedEntry, selectedRow);
  const bars = useBarsDocument(session, live ? config.barsRefetchMs : undefined);
  // Which card is highlighted. A session the operator named is itself, so the
  // card responds to the click rather than to the megabyte that follows it;
  // only the `latest` sentinel waits for the route to say which session it
  // resolved, which is what keeps a card selected on first paint.
  const active =
    session === LATEST_SESSION ? (bars.response?.session ?? session) : session;

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

      {fetchFailed && (
        <div
          role="alert"
          className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
        >
          <p className="font-semibold">
            {authError ? '조회 인증을 확인해 주세요' : '상태 조회 연결 오류'}
          </p>
          <p className="mt-1 text-sm">
            {authError
              ? 'API 키 또는 접근 권한을 확인한 후 다시 조회해 주세요.'
              : '연결을 확인한 후 다시 조회해 주세요. 남아 있는 값은 마지막 조회 기록입니다.'}
          </p>
        </div>
      )}

      <StatusStrip
        projectionState={state}
        projection={projection}
        projectionAgeSeconds={age}
        status={status}
        symbols={symbols}
        stateLabel={labels[state]}
      />

      <TenantCards sessions={sessions} symbols={symbols} selected={active} onSelect={setSession} />
      <SessionPicker sessions={sessions} value={session} onChange={setSession} />

      {/* Three views of ONE session: the evidence a decision rests on, what was
          traded, and what stopped. They share the page's bars read, so a
          megabyte is fetched once rather than once per section. */}
      <BarsPanel
        key={active}
        requested={session}
        read={bars}
        refetchMs={live ? config.barsRefetchMs : undefined}
      />
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
