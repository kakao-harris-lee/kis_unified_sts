"use client";

import { useQueries } from '@tanstack/react-query';
import {
  groupSessionsByDate,
  hasHypotheticalPnl,
  isAcceptedBarsDocument,
  sessionKindLabel,
  type TosBarsDocument,
  type TosSessionEntry,
} from '@/lib/dashboard/tosBars';
import {
  bestEntryProgress,
  entryProgress,
  latestCountedBar,
  latestInWindowProgress,
  probePredicate,
  probeTally,
  type ProgressAt,
} from '@/lib/dashboard/tosDecision';
import { glossaryLabel } from '@/lib/dashboard/tosGlossary';
import {
  PNL_CLASSES,
  PNL_WORDS,
  countLabel,
  pnlFigure,
  pointsLabel,
} from '@/lib/dashboard/tosMoney';
import { sessionPhase, type TosSymbolPnl, type TosSymbolRow } from '@/lib/dashboard/tosSymbols';
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
 * `null` row means the per-symbol document carries nothing about that tenant —
 * a session the export has not seen at all. That is 「기록 없음」, never 「종료」:
 * the second would be a claim about a session this page cannot see. Since the
 * export learned the futures rows (P2), a decision-only tenant has a real
 * status here too, so this no longer stands in for «선물».
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

/** `08:46` → `08:46`; a bare `HH:MM:SS` keeps its seconds off the card. */
function clock(value: string | null | undefined): string | null {
  if (!value) return null;
  return value.length >= 5 ? value.slice(0, 5) : value;
}

/**
 * One realized figure, with its sign, its word and its hue — in that order.
 *
 * The hue is `--color-profit` (red) or `--color-loss` (blue), the Korean
 * convention, and it is never alone: the sign is printed and the word follows,
 * so the number reads the same in greyscale.
 */
function Money({ krw, className }: { krw: string | null | undefined; className?: string }) {
  const figure = pnlFigure(krw);
  if (!figure) return <span className="text-slate-500 dark:text-slate-400">알 수 없음</span>;
  return (
    <span className={`${PNL_CLASSES[figure.direction]} ${className ?? ''}`}>
      <span className="font-semibold tabular-nums">{figure.signed}원</span>{' '}
      <span className="text-xs">{PNL_WORDS[figure.direction]}</span>
    </span>
  );
}

/**
 * A stock tenant's realized PnL — today, then the running total.
 *
 * `pnl` absent is «손익 기록 없음», never a zero: the document sends null when
 * the leaf could not be read, and a zero there would claim the tenant traded
 * and broke even. A basis other than the broker's execution price is named,
 * because a figure built on a sealed limit price is a different claim.
 */
function RealizedPnl({ pnl }: { pnl: TosSymbolPnl | null | undefined }) {
  if (!pnl) {
    return (
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        <Term name="realized_pnl">실현 손익</Term> 기록 없음
      </p>
    );
  }
  const today = pnl.today;
  const cumulative = pnl.cumulative;
  const basis = today?.pnl_basis;
  // One line, because this sits above the fold: the day's figure beside the
  // fills it came from, and the running total in the small line under it.
  return (
    <p className="mt-1 flex flex-wrap items-baseline gap-x-2 text-xs">
      <span className="text-slate-500 dark:text-slate-400">누적</span>
      <Money krw={cumulative?.pnl_krw} />
      <span className="text-slate-500 dark:text-slate-400">
        <Term name="round_trip">왕복</Term> {countLabel(cumulative?.closed_round_trips)} · 승{' '}
        {countLabel(cumulative?.wins, '')}
      </span>
      {basis != null && basis !== 'EXECUTION' && (
        <span className="text-slate-500 dark:text-slate-400">
          <Term name={basis} />
        </span>
      )}
    </p>
  );
}

/** Today's realized figure, as the fourth cell of the card's fills row. */
function TodayPnl({ pnl }: { pnl: TosSymbolPnl | null | undefined }) {
  return (
    <div>
      <dt className="text-slate-500 dark:text-slate-400">
        오늘 <Term name="realized_pnl">손익</Term>
      </dt>
      <dd>
        <Money krw={pnl?.today?.pnl_krw} />
      </dd>
    </div>
  );
}

/**
 * What a decision-only tenant's judgements WOULD have earned, had they filled.
 *
 * Outlined and dashed, with its own label and the assumptions on the chip, so
 * it cannot be mistaken for the realized figure above: the three assumptions
 * (a guaranteed fill, no fees, no slippage) all push the number the same
 * flattering way. A session that decided nothing says «진입 없음» — never
 * «0원», which would read as «traded and broke even».
 */
function HypotheticalPnl({ document }: { document: TosBarsDocument | null }) {
  if (!hasHypotheticalPnl(document)) return null;
  const block = document?.hypothetical_pnl;
  const totals = block?.totals;
  const assumptions = (block?.assumptions ?? []).map((code) => glossaryLabel(code)).join(' · ');
  const empty = totals == null || totals.trades === 0 || totals.hypothetical_pnl_krw == null;
  return (
    <div className="mt-3">
      {/* Dashed outline, its own label and the assumptions on hover: never the
          same visual language as the realized figure on a stock card. */}
      <p
        className="inline-flex flex-wrap items-baseline gap-x-2 rounded-lg border border-dashed border-slate-400 px-2 py-1 text-sm dark:border-slate-500"
        title={assumptions ? `체결 가정: ${assumptions}` : undefined}
      >
        <span className="text-xs text-slate-500 dark:text-slate-400">
          <Term name="hypothetical_pnl">가상 손익(체결 가정)</Term>
        </span>
        {empty ? (
          <span className="font-medium">진입 없음</span>
        ) : (
          <>
            <span className="tabular-nums font-medium">{pointsLabel(totals?.points)}</span>
            <Money krw={totals?.hypothetical_pnl_krw} />
            <span className="text-xs text-slate-500 dark:text-slate-400">
              <Term name="round_trip">왕복</Term> {countLabel(totals?.trades)} · 승{' '}
              {countLabel(totals?.wins, '')}
            </span>
          </>
        )}
      </p>
    </div>
  );
}

/** «n/m 충족 · HH:MM», or null when the tenant has no judged in-window bar. */
function ProgressLine({ at, label }: { at: ProgressAt | null; label: string }) {
  if (!at) return null;
  return (
    <p className="mt-1 text-sm">
      <span className="text-slate-500 dark:text-slate-400">{label} </span>
      <span className="font-medium">
        {at.progress.passed}/{at.progress.total} 충족
      </span>
      <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
        {at.timeKst ? `${at.timeKst} 봉` : '시각 알 수 없음'}
      </span>
    </p>
  );
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
 * One tenant, answering «진입에 얼마나 가까웠나» before any chart is read.
 *
 * Two numbers, both over the bars the engine actually JUDGED and whose entry
 * window was open: the closest the day ever came, with the time it came
 * closest, and where the last in-window bar stood. Reporting the last bar of
 * the file instead would mean every card reads the same 1/5 every evening —
 * after 15:15 the session ends on EOD bars whose entry window is shut, and the
 * card would answer a question nobody asked.
 */
function TenantCard({ entry, row, document, loading, selected, onSelect }: CardProps) {
  const futures = entry.kind === 'futures';
  const bars = document?.bars ?? null;
  // The document's own probe flags when it carries them — see probePredicate.
  const isProbe = probePredicate(document);
  const best = bestEntryProgress(bars, isProbe);
  const latest = latestInWindowProgress(bars, isProbe);
  // Nothing inside the window was ever judged (a session that never opened, or
  // a tenant that publishes no window): fall back to the last judged bar, and
  // say that is what it is.
  const fallback = best ? null : entryProgress(latestCountedBar(bars), isProbe);
  const run = runStateOf(row);
  const probes = probeTally(bars, isProbe);
  const unresolved = row?.pnl?.unresolved?.count ?? 0;

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
            <Badge tone="neutral">
              <Term name="decision_only" />
            </Badge>
          ) : (
            <Badge tone="neutral">
              <Term name="mock_account" />
            </Badge>
          )}
          {/* Both numbers, always: the probe fired 325 times on 005930 and one
              order left. 「325회」 alone reads as 325 trades. */}
          {probes.fired > 0 && (
            <Badge tone="warn" title="R4-M2-PROBE-ENTRY-LONG">
              <Term name="R4-M2-PROBE-ENTRY-LONG" /> 발화 {probes.fired}봉 · 게이트 통과{' '}
              {probes.passed}
            </Badge>
          )}
          {/* Orders the FIFO could not account for. They are NOT in the PnL
              below, so the count has to be on the card beside it. */}
          {unresolved > 0 && (
            <Badge tone="warn">
              <Term name="unresolved_order">미해결 주문</Term> {unresolved}건
            </Badge>
          )}
        </div>

        <p className="mt-2 text-sm">
          <Badge tone={RUN_TONES[run.state]}>
            {run.label}
            {run.detail ? ` · ${run.detail}` : ''}
          </Badge>
          {(row?.session?.boot_at || row?.session?.end_at) && (
            <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
              {row.session.boot_at ? `부팅 ${clock(row.session.boot_at)}` : '부팅 기록 없음'}
              {row.session.end_at ? ` · 종료 ${clock(row.session.end_at)}` : ''}
            </span>
          )}
        </p>

        <div className="mt-3">
          {loading ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">진입 조건 불러오는 중</p>
          ) : best ? (
            <>
              <ProgressLine at={best} label="가장 근접" />
              {/* Only when it differs: on a day whose closest bar IS the last
                  one, a second identical line is noise. */}
              {latest && latest.timeKst !== best.timeKst && (
                <ProgressLine at={latest} label="마지막 진입 시간대" />
              )}
            </>
          ) : fallback ? (
            <p className="text-sm">
              <span className="text-slate-500 dark:text-slate-400">진입 시간대 봉 없음 · 마지막 판단 </span>
              <span className="font-medium">
                {fallback.passed}/{fallback.total} 충족
              </span>
            </p>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">진입 조건 알 수 없음</p>
          )}
        </div>
        {best && best.progress.failing.length > 0 && (
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
            가장 근접했을 때 못 채운 조건: {best.progress.failing.join(' · ')}
          </p>
        )}

        {futures ? (
          <>
            {/* The chip appears only when the export carried the block; the
                sentence always does, because «판단 전용» is true of this tenant
                whether or not the figure could be computed. */}
            <HypotheticalPnl document={document} />
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              주문을 내지 않는 tenant 입니다 — 체결도 보유도 없고, 가상 손익은 실현 손익과
              합산하지 않습니다.
            </p>
          </>
        ) : (
          <>
            {/* Today's realized figure sits in the fills row rather than under
                it: this card is above the fold, and the day's PnL belongs
                beside the orders that produced it. */}
            <dl className="mt-3 grid grid-cols-4 gap-2 text-xs">
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
              <TodayPnl pnl={row?.pnl} />
            </dl>
            <RealizedPnl pnl={row?.pnl} />
          </>
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
