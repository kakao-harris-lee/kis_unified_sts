"use client";

import { useQueries } from '@tanstack/react-query';
import {
  groupSessionsByDate,
  isAcceptedBarsDocument,
  sessionKindLabel,
  type TosBarsDocument,
  type TosSessionEntry,
} from '@/lib/dashboard/tosBars';
import { entryProgress, isProbeRule, latestCountedBar } from '@/lib/dashboard/tosDecision';
import { sessionPhase, type TosSymbolRow } from '@/lib/dashboard/tosSymbols';
import { AsOf, Badge, ageLabel, type Tone } from './marks';
import Term from './Term';
import { barsQueryOptions, type SessionsRead, type SymbolsRead } from './queries';

interface TenantCardsProps {
  sessions: SessionsRead;
  symbols: SymbolsRead;
  /** The session the sections below are showing. */
  selected: string;
  onSelect: (session: string) => void;
}

/** The three run states an operator distinguishes, per requirement 6. */
type RunState = 'running' | 'attention' | 'done' | 'unknown';

const RUN_TONES: Record<RunState, Tone> = {
  running: 'good',
  attention: 'warn',
  done: 'neutral',
  unknown: 'neutral',
};

/**
 * A tenant's run state from its symbols row.
 *
 * `null` row means this document carries nothing about that tenant — true of
 * every futures tree, because the per-symbol export covers the stock tenants
 * only. That is 「기록 없음」, never 「종료」: the second would be a claim about a
 * session this page cannot see.
 */
function runStateOf(row: TosSymbolRow | null): {
  state: RunState;
  label: string;
  detail: string | null;
} {
  if (!row) return { state: 'unknown', label: '상태 기록 없음', detail: null };
  if (row.error != null) {
    return { state: 'attention', label: '대기 · 차단', detail: '기록을 읽지 못했습니다' };
  }
  const phase = sessionPhase(row.session);
  if (phase === 'running') {
    return { state: 'running', label: '진행 중', detail: row.session?.status ?? null };
  }
  // 「종료」 and 「시작 안 함」 are one state for the operator — nothing is
  // running and nothing needs looking at — but the card still says which.
  if (phase === 'settled') return { state: 'done', label: '종료', detail: null };
  if (phase === 'none') return { state: 'done', label: '시작 안 함', detail: null };
  return { state: 'attention', label: '대기 · 차단', detail: row.session?.status ?? null };
}

function probeFires(document: TosBarsDocument | null): number {
  const decisions = document?.summary?.decisions ?? null;
  if (!decisions) return 0;
  return Object.entries(decisions)
    .filter(([ruleId]) => isProbeRule(ruleId))
    .reduce((total, [, count]) => total + count, 0);
}

interface CardProps {
  entry: TosSessionEntry;
  row: TosSymbolRow | null;
  document: TosBarsDocument | null;
  loading: boolean;
  selected: boolean;
  onSelect: (session: string) => void;
}

/**
 * One tenant, answering «진입에 얼마나 가까운가» before any chart is read.
 *
 * The progress is taken from the LAST bar the engine actually judged, not from
 * the last bar in the file: a withheld tail would otherwise report 「0/5」 for a
 * tenant whose final judged bar met four conditions.
 */
function TenantCard({ entry, row, document, loading, selected, onSelect }: CardProps) {
  const futures = entry.kind === 'futures';
  const bar = latestCountedBar(document?.bars);
  const progress = entryProgress(bar);
  const run = runStateOf(row);
  const probes = probeFires(document);

  return (
    <li className="min-w-0">
      <label
        className={`block min-w-0 cursor-pointer rounded-xl border p-4 transition ${
          selected
            ? 'border-slate-900 bg-slate-50 dark:border-slate-200 dark:bg-slate-800'
            : 'border-slate-200 bg-white hover:border-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-600'
        }`}
      >
        <input
          type="radio"
          name="tos-tenant"
          value={entry.session}
          checked={selected}
          onChange={() => onSelect(entry.session)}
          className="sr-only"
        />
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{sessionKindLabel(entry)}</span>
          {futures ? (
            <Badge tone="info">
              <Term name="decision_only" />
            </Badge>
          ) : (
            <Badge tone="info">
              <Term name="mock_account" />
            </Badge>
          )}
          {probes > 0 && (
            <Badge tone="warn" title="R4-M2-PROBE-ENTRY-LONG">
              <Term name="R4-M2-PROBE-ENTRY-LONG" /> {probes}회
            </Badge>
          )}
        </div>

        <p className="mt-2 text-sm">
          <Badge tone={RUN_TONES[run.state]}>
            {run.label}
            {run.detail ? ` · ${run.detail}` : ''}
          </Badge>
        </p>

        <p className="mt-3 text-sm">
          {loading ? (
            <span className="text-slate-500 dark:text-slate-400">진입 조건 불러오는 중</span>
          ) : progress ? (
            <>
              <span className="font-medium">
                진입 조건 {progress.passed}/{progress.total} 충족
              </span>
              <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
                {bar?.time_kst ? `${bar.time_kst} 봉 기준` : '시각 알 수 없음'}
              </span>
            </>
          ) : (
            <span className="text-slate-500 dark:text-slate-400">진입 조건 알 수 없음</span>
          )}
        </p>
        {progress && progress.failing.length > 0 && (
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
            못 채운 조건: {progress.failing.join(' · ')}
          </p>
        )}

        {futures ? (
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            주문을 내지 않는 tenant 입니다 — 체결도 보유도 없습니다.
          </p>
        ) : (
          <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <div>
              <dt className="text-slate-500 dark:text-slate-400">매수</dt>
              <dd>{row?.buy?.fills == null ? '알 수 없음' : `${row.buy.fills}건`}</dd>
            </div>
            <div>
              <dt className="text-slate-500 dark:text-slate-400">매도</dt>
              <dd>{row?.sell?.fills == null ? '알 수 없음' : `${row.sell.fills}건`}</dd>
            </div>
            <div>
              <dt className="text-slate-500 dark:text-slate-400">
                <Term name="TOS_LEDGER_FIFO_OPEN_LOTS">보유</Term>
              </dt>
              <dd>{row?.holding?.quantity == null ? '알 수 없음' : `${row.holding.quantity}주`}</dd>
            </div>
          </dl>
        )}

        <AsOf>
          {entry.date ?? '날짜 없음'} · {ageLabel(entry.age_seconds)}
        </AsOf>
      </label>
    </li>
  );
}

/**
 * «tenant 별로 지금 어디까지 왔나» — one card per session of the newest exported
 * trading day.
 *
 * COST, stated rather than hidden: the entry progress can only come from the
 * tenant's own bars document, so this component reads one document per card.
 * They are the same cache entries the panels below use (`barsQueryOptions`),
 * so the selected tenant's document is fetched once for the whole page, and
 * only the newest day's sessions are read — never the whole listing. A
 * per-session summary on the API would remove the rest of the cost, and that is
 * phase 2's job, not a reason to show a number this page cannot support.
 */
export default function TenantCards({ sessions, symbols, selected, onSelect }: TenantCardsProps) {
  const groups = groupSessionsByDate(sessions.sessions);
  // The route orders newest day first and grouping preserves that order.
  const today = groups[0]?.sessions ?? [];

  const documents = useQueries({
    queries: today.map((entry) => barsQueryOptions(entry.session)),
  });

  const rows = symbols.document?.symbols ?? [];
  const rowFor = (session: string): TosSymbolRow | null =>
    rows.find((row) => row.session?.name === session) ?? null;

  return (
    <section
      aria-label="tenant 현황"
      className="min-w-0 space-y-3"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="font-semibold">tenant 별 현황</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          종목·방향마다 진입 조건을 몇 개나 채웠는지 봅니다. 카드를 고르면 아래 세 칸이 그 세션을 설명합니다.
        </p>
      </div>

      {today.length === 0 ? (
        <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          {sessions.failed
            ? '세션 목록을 가져오지 못했습니다. 아래에서 세션 이름으로 조회해 주세요.'
            : '내보낸 세션이 아직 없습니다.'}
        </p>
      ) : (
        <ul
          role="radiogroup"
          aria-label="tenant 선택"
          className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-3"
        >
          {today.map((entry, index) => {
            const query = documents[index];
            const response = query?.data;
            const document =
              response?.available && isAcceptedBarsDocument(response.document) ? response.document : null;
            return (
              <TenantCard
                key={entry.session}
                entry={entry}
                row={rowFor(entry.session)}
                document={document}
                loading={query?.isPending === true}
                selected={entry.session === selected}
                onSelect={onSelect}
              />
            );
          })}
        </ul>
      )}
    </section>
  );
}
