"use client";

import { useState, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import BarsChart from './BarsChart';
import BarsRuleBands from './BarsRuleBands';
import BarsSummaryTable from './BarsSummaryTable';
import {
  LATEST_SESSION,
  barsState,
  isAcceptedBarsDocument,
  tosBarsApi,
  type BarsState,
} from '@/lib/dashboard/tosBars';

const labels: Record<BarsState, string> = {
  loading: '바 기록을 불러오는 중',
  error: '바 기록 조회 연결 오류',
  missing: '이 세션의 바 기록이 아직 없습니다',
  unreadable: '바 기록 파일을 열지 못했습니다',
  invalid: '바 기록 형식 오류',
  unsupported: '지원하지 않는 바 기록 버전',
  'bad-request': '세션 이름을 확인해 주세요',
  unknown: '바 기록 확인 불가',
  ready: '바 기록을 조회했습니다',
};

const hints: Record<BarsState, string> = {
  loading: '',
  error: '연결을 확인한 후 다시 조회해 주세요.',
  missing: '호스트에서 `sts tos export-bars <세션>` 을 실행하면 이 화면에 나타납니다.',
  unreadable: '내보낸 파일의 경로와 접근 권한을 확인해 주세요. 파일 내용의 문제가 아닙니다.',
  invalid: '내보내기 도구와 조회 서비스의 형식을 확인해 주세요.',
  unsupported: '내보내기 도구와 조회 서비스의 버전을 확인해 주세요.',
  'bad-request': '세션 디렉터리 이름(예: stock-r1-20261110)이나 latest 를 입력해 주세요.',
  unknown: '값이 없으면 알 수 없음으로 표시합니다.',
  ready: '',
};

/**
 * Read-only per-bar panel: «왜 이 바에서 이 결정이었나» (roadmap §P1).
 *
 * The document is produced on the host by `sts tos export-bars` and read by the
 * Control Plane purely as a file — this panel never reaches the kernel, the
 * session stores, or any authority surface. Nothing here can issue a command.
 */
export default function BarsPanel() {
  const [requested, setRequested] = useState(LATEST_SESSION);
  const [draft, setDraft] = useState('');
  const query = useQuery({
    queryKey: ['tos-session-bars', requested],
    queryFn: () => tosBarsApi.getBars(requested),
    retry: false,
  });

  const response = query.data;
  const state = barsState(response, query.isError || query.fetchStatus === 'paused');
  // The same acceptance predicate the banner uses — see isAcceptedBarsDocument.
  const document =
    response?.available && isAcceptedBarsDocument(response.document)
      ? response.document
      : null;
  const httpStatus = isAxiosError(query.error) ? query.error.response?.status : undefined;
  const authError = httpStatus === 401 || httpStatus === 403;
  const warning = state !== 'ready' && state !== 'loading';

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setRequested(draft.trim() || LATEST_SESSION);
  };

  return (
    <section
      aria-label="바별 결정 점검"
      className="min-w-0 space-y-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="font-semibold">바별 결정 점검 · 읽기 전용</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            기록된 세션의 봉마다 엔진이 평가한 값 · 규칙별 통과 · 결정과 정지를 봅니다.
          </p>
        </div>
        <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
          <label htmlFor="bars-session" className="text-sm text-slate-500 dark:text-slate-400">
            세션
          </label>
          <input
            id="bars-session"
            name="session"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={LATEST_SESSION}
            className="w-48 rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-950"
          />
          <button
            type="submit"
            disabled={query.isFetching}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-slate-700"
          >
            조회
          </button>
        </form>
      </div>

      <div
        role={warning ? 'alert' : 'status'}
        className={`rounded-lg border p-3 text-sm ${
          warning
            ? 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100'
            : 'border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950'
        }`}
      >
        <p className="font-semibold">
          {authError ? '조회 인증을 확인해 주세요' : labels[state]}
        </p>
        {(authError || hints[state]) && (
          <p className="mt-1">
            {authError ? 'API 키 또는 접근 권한을 확인한 후 다시 조회해 주세요.' : hints[state]}
          </p>
        )}
        <p className="mt-2 text-xs">
          요청한 세션: {requested}
          {response?.session && response.session !== requested
            ? ` · 조회된 세션: ${response.session}`
            : ''}
          {response?.age_seconds != null
            ? ` · 내보낸 뒤 ${Math.floor(response.age_seconds)}초`
            : ''}
        </p>
      </div>

      {document && (
        <div className="min-w-0 space-y-5">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-500 dark:text-slate-400">
            <span>세션: {document.session ?? '알 수 없음'}</span>
            <span>종목: {document.instrument ?? '알 수 없음'}</span>
            <span>전략 sha256: {document.strategy?.sha256?.slice(0, 12) ?? '알 수 없음'}</span>
            <span>
              바인딩:{' '}
              {document.bindings?.values
                ? Object.entries(document.bindings.values)
                    .map(([key, value]) => `${key}=${value}`)
                    .join(' · ')
                : '알 수 없음'}
            </span>
          </div>
          <BarsChart bars={document.bars ?? []} />
          <BarsRuleBands
            bars={document.bars ?? []}
            rules={document.summary?.rules ?? []}
          />
          {document.summary && <BarsSummaryTable summary={document.summary} />}
        </div>
      )}
    </section>
  );
}
