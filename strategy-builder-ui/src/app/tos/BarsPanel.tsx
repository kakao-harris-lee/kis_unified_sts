"use client";

import { useState } from 'react';
import type { BarsState } from '@/lib/dashboard/tosBars';
import { latestCountedBar } from '@/lib/dashboard/tosDecision';
import BarsChart from './BarsChart';
import BlockingConditions from './BlockingConditions';
import DecisionEvidence from './DecisionEvidence';
import VerdictTimeline from './VerdictTimeline';
import { AsOf, ageLabel } from './marks';
import type { BarsRead } from './queries';

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

interface BarsPanelProps {
  /** The session id the operator asked for. */
  requested: string;
  read: BarsRead;
}

/**
 * «왜 진입했나 / 안 했나» — the evidence one session's decisions rest on.
 *
 * The document is produced on the host by `sts tos export-bars` and read by
 * the Control Plane purely as a file — this panel never reaches the kernel,
 * the session stores, or any authority surface, and nothing here can issue a
 * command. The chart, the checklist and the timeline are three views of the
 * same selected bar, so an operator can move between «언제» and «왜» without
 * re-finding their place.
 *
 * The bar it opens on is the last one the engine actually JUDGED, not the last
 * one in the file: a withheld tail would otherwise greet the operator with a
 * bar that has no conditions to show.
 */
export default function BarsPanel({ requested, read }: BarsPanelProps) {
  const { state, document, response, authError } = read;
  const bars = document?.bars ?? [];
  const defaultIndex = Math.max(0, bars.indexOf(latestCountedBar(bars) ?? bars[bars.length - 1]));
  const [chosen, setChosen] = useState<number | null>(null);
  const selectedIndex = chosen == null ? defaultIndex : Math.min(chosen, Math.max(0, bars.length - 1));
  const warning = state !== 'ready' && state !== 'loading';

  return (
    <section
      aria-label="판단 근거"
      className="min-w-0 space-y-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="min-w-0">
        <h2 className="font-semibold">판단 근거</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          왜 진입했나 / 안 했나 — 고른 봉에서 어떤 조건이 서고 무엇이 막았는지 봅니다.
        </p>
      </div>

      <div
        role={warning ? 'alert' : 'status'}
        className={`rounded-lg border p-3 text-sm ${
          warning
            ? 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100'
            : 'border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950'
        }`}
      >
        <p className="font-semibold">{authError ? '조회 인증을 확인해 주세요' : labels[state]}</p>
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
          {response?.age_seconds != null ? ` · ${ageLabel(response.age_seconds)}` : ''}
        </p>
      </div>

      {document && (
        <div className="min-w-0 space-y-5">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-500 dark:text-slate-400">
            <span>세션: {document.session ?? '알 수 없음'}</span>
            <span>종목: {document.instrument ?? '알 수 없음'}</span>
            <span>
              구간:{' '}
              {bars.length
                ? `${bars[0].time_kst ?? '알 수 없음'} – ${bars[bars.length - 1].time_kst ?? '알 수 없음'}`
                : '알 수 없음'}
            </span>
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

          <BarsChart bars={bars} selectedIndex={selectedIndex} onSelect={setChosen} />
          <DecisionEvidence bar={bars[selectedIndex] ?? null} summary={document.summary} />
          <BlockingConditions summary={document.summary} />
          <VerdictTimeline bars={bars} selectedIndex={selectedIndex} onSelect={setChosen} />

          <AsOf>
            이 기록은 세션이 끝난 뒤 한 번 내보낸 것입니다. 장중에는 직전 세션을 보고 있을 수
            있습니다.
          </AsOf>
        </div>
      )}
    </section>
  );
}
