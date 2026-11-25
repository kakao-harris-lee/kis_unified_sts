"use client";

import {
  ORDER_BAR_TIME_BASIS,
  TOS_LEDGER_HOLDING_BASIS,
  isDecisionOnlyRow,
  isTodaysDocument,
  sessionPhase,
  tradingRows,
  type SessionPhase,
  type SymbolsState,
  type TosSymbolFill,
  type TosSymbolHalt,
  type TosSymbolHolding,
  type TosSymbolPnlPeriod,
  type TosSymbolRow,
  type TosSymbolSession,
  type TosSymbolSide,
  type TosSymbolUnresolvedAttempt,
} from '@/lib/dashboard/tosSymbols';
import {
  PNL_CLASSES,
  PNL_WORDS,
  UNKNOWN,
  countLabel,
  pnlFigure,
  quantityLabel,
} from '@/lib/dashboard/tosMoney';
import { AsOf, Badge, ageLabel } from './marks';
import Term from './Term';
import type { SymbolsRead } from './queries';

const labels: Record<SymbolsState, string> = {
  loading: '거래 현황을 불러오는 중',
  error: '거래 현황 조회 연결 오류',
  missing: '아직 거래 현황이 내보내지지 않았습니다',
  unreadable: '거래 현황 파일을 열지 못했습니다',
  invalid: '거래 현황 형식 오류',
  unsupported: '지원하지 않는 거래 현황 버전',
  unknown: '거래 현황 확인 불가',
  ready: '거래 현황을 조회했습니다',
};

const hints: Record<SymbolsState, string> = {
  loading: '',
  error: '연결을 확인한 후 다시 조회해 주세요. 남아 있는 값은 마지막 조회 기록입니다.',
  missing: '호스트에서 `sts tos export-symbols` 를 실행하면 이 화면에 나타납니다.',
  unreadable: '내보낸 파일의 경로와 접근 권한을 확인해 주세요. 파일 내용의 문제가 아닙니다.',
  invalid: '내보내기 도구와 조회 서비스의 형식을 확인해 주세요.',
  unsupported: '내보내기 도구와 조회 서비스의 버전을 확인해 주세요.',
  unknown: '값이 없으면 알 수 없음으로 표시합니다.',
  ready: '',
};

const phaseLabels: Record<SessionPhase, string> = {
  running: '진행 중',
  settled: '종료',
  none: '오늘 시작 안 함',
  unknown: '확인 필요',
};

/** A decimal string from the exporter, grouped. Unparseable text is shown as-is. */
function money(value: string | null | undefined): string {
  if (value == null) return '알 수 없음';
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString('ko-KR') : value;
}

function count(value: number | null | undefined): string {
  return value == null ? '알 수 없음' : String(value);
}

/**
 * One fill's price, saying which basis it came from.
 *
 * The same distinction `sts tos perf` prints: the broker's average execution
 * price when the evidence has one, otherwise the sealed order's limit price.
 * Showing a limit price as though it were a fill price would overstate what is
 * known, so the basis is always on screen beside the number.
 */
function priceLabel(fill: TosSymbolFill): string {
  if (fill.execution_price_krw != null) return `체결가 ${money(fill.execution_price_krw)}`;
  if (fill.order_price_krw != null) return `지정가 ${money(fill.order_price_krw)}`;
  return '가격 모름';
}

function SideCell({ side }: { side: TosSymbolSide | null | undefined }) {
  const fills = side?.fills;
  if (fills == null) return <span className="text-slate-500 dark:text-slate-400">알 수 없음</span>;
  if (fills === 0) return <span className="text-slate-500 dark:text-slate-400">없음</span>;
  const last = side?.last;
  return (
    <div className="space-y-0.5">
      <div className="font-medium">
        {fills}건 · {side?.quantity ?? '?'}주
      </div>
      {last && (
        <div className="text-xs text-slate-500 dark:text-slate-400">
          {priceLabel(last)}
          {/* 「주문 봉」 is a claim about where the time came from, so it is
              printed only while the document still says ORDER_BAR. A future
              basis prints its own name rather than inheriting this label. */}
          {last.time_kst == null
            ? ' · 시각 없음'
            : last.time_basis === ORDER_BAR_TIME_BASIS
              ? ` · 주문 봉 ${last.time_kst}`
              : ` · ${last.time_basis ?? '기준 모름'} ${last.time_kst}`}
          {last.broker_execution_id ? ` · ${last.broker_execution_id}` : ''}
        </div>
      )}
    </div>
  );
}

function HoldingCell({ holding }: { holding: TosSymbolHolding | null | undefined }) {
  if (holding?.quantity == null) {
    return <span className="text-slate-500 dark:text-slate-400">알 수 없음</span>;
  }
  const open = Number(holding.quantity) > 0;
  return (
    <div className="space-y-0.5">
      <div className={open ? 'font-medium' : 'text-slate-500 dark:text-slate-400'}>
        {holding.quantity}주
      </div>
      {open && holding.lots != null && (
        <div className="text-xs text-slate-500 dark:text-slate-400">{holding.lots} lot</div>
      )}
    </div>
  );
}

function HaltCell({ halt }: { halt: TosSymbolHalt | null | undefined }) {
  if (halt?.error != null) {
    return <span className="text-amber-700 dark:text-amber-300">읽지 못함 · {halt.error}</span>;
  }
  const flow = halt?.last_flow;
  const withheld = halt?.last_withheld;
  if (!flow && !withheld) {
    return <span className="text-slate-500 dark:text-slate-400">없음</span>;
  }
  return (
    <div className="space-y-0.5">
      {flow ? (
        <div className="font-medium">
          <Term name={flow.reason} />
          {flow.time_kst ? ` · ${flow.time_kst}` : ''}
          {flow.step ? (
            <span className="font-normal text-slate-500 dark:text-slate-400">
              {' · '}
              <Term name={flow.step} />
            </span>
          ) : null}
        </div>
      ) : (
        <div className="text-slate-500 dark:text-slate-400">흐름 정지 없음</div>
      )}
      {withheld && (
        <div className="text-xs text-slate-500 dark:text-slate-400">
          보류 <Term name={withheld.reason} />
          {withheld.time_kst ? ` · ${withheld.time_kst}` : ''}
        </div>
      )}
    </div>
  );
}

function SessionCell({
  session,
  ticks,
}: {
  session: TosSymbolSession | null | undefined;
  ticks: number | null | undefined;
}) {
  const phase = sessionPhase(session);
  return (
    <div className="space-y-1">
      <Badge tone={phase === 'running' ? 'good' : phase === 'unknown' ? 'warn' : 'neutral'}>
        {phaseLabels[phase]}
        {/* The raw status rides along for every phase but "none": ENDED and
            FAILED are both settled-ish, and the operator needs the difference. */}
        {phase !== 'none' && session?.status ? ` · ${session.status}` : ''}
      </Badge>
      <div className="text-xs text-slate-500 dark:text-slate-400">
        {session?.boot_at ? `부팅 ${session.boot_at}` : '부팅 기록 없음'}
        {session?.end_at ? ` · 종료 ${session.end_at}` : ''}
        {session?.run_rc != null ? ` · rc=${session.run_rc}` : ''}
      </div>
      <div className="text-xs text-slate-500 dark:text-slate-400">틱 {count(ticks)}</div>
    </div>
  );
}

/**
 * One realized figure — sign, hue, word.
 *
 * `null` is «알 수 없음» and never 0: an unreadable leaf and a tenant that
 * cannot trade both send null, and a zero would read as «traded and broke
 * even» for either of them.
 */
function Money({ krw }: { krw: string | null | undefined }) {
  const figure = pnlFigure(krw);
  if (!figure) return <span className="text-slate-500 dark:text-slate-400">{UNKNOWN}</span>;
  return (
    <span className={PNL_CLASSES[figure.direction]}>
      <span className="font-semibold tabular-nums">{figure.signed}원</span>{' '}
      <span className="text-xs">{PNL_WORDS[figure.direction]}</span>
    </span>
  );
}

/** The PnL cell, naming its basis whenever it is not the broker's fill price. */
function PnlCell({ period }: { period: TosSymbolPnlPeriod | null | undefined }) {
  if (!period) return <span className="text-slate-500 dark:text-slate-400">{UNKNOWN}</span>;
  const basis = period.pnl_basis;
  return (
    <div className="space-y-0.5">
      <Money krw={period.pnl_krw} />
      {basis != null && basis !== 'EXECUTION' && (
        <div className="text-xs text-slate-500 dark:text-slate-400">
          <Term name={basis} />
        </div>
      )}
    </div>
  );
}

function SymbolRowCells({ row }: { row: TosSymbolRow }) {
  const decisionOnly = isDecisionOnlyRow(row);
  const today = row.pnl?.today;
  const cumulative = row.pnl?.cumulative;
  return (
    <tr className="border-t border-slate-200 align-top dark:border-slate-800">
      <th scope="row" className="py-3 pr-3 text-left font-semibold">
        {row.symbol ?? '알 수 없음'}
        {row.direction ? (
          <span className="block text-xs font-normal text-slate-500 dark:text-slate-400">
            {row.direction}
          </span>
        ) : null}
      </th>
      <td className="py-3 pr-3">
        <SessionCell session={row.session} ticks={row.ticks} />
      </td>
      {row.error != null ? (
        <td className="py-3 pr-3 text-amber-700 dark:text-amber-300" colSpan={7}>
          기록을 읽지 못했습니다 · {row.error}
        </td>
      ) : decisionOnly ? (
        // One cell, not six «해당 없음»: this tenant stops at an independent
        // approval step and has no order, no fill and no realized figure to
        // report. Six zeros would read as «traded nothing today».
        <td className="py-3 pr-3" colSpan={7}>
          <Badge tone="neutral">
            <Term name="decision_only" />
          </Badge>
          <span className="ml-2 text-slate-500 dark:text-slate-400">
            주문·체결·손익 해당 없음 — 판단만 기록합니다
          </span>
        </td>
      ) : (
        <>
          <td className="py-3 pr-3">
            <SideCell side={row.buy} />
          </td>
          <td className="py-3 pr-3">
            <SideCell side={row.sell} />
          </td>
          <td className="py-3 pr-3">
            <HoldingCell holding={row.holding} />
          </td>
          <td className="py-3 pr-3">
            <PnlCell period={today} />
          </td>
          <td className="py-3 pr-3">
            <PnlCell period={cumulative} />
          </td>
          <td className="py-3 pr-3 tabular-nums">
            {countLabel(today?.closed_round_trips)}
            <span className="block text-xs text-slate-500 dark:text-slate-400">
              누적 {countLabel(cumulative?.closed_round_trips)}
            </span>
          </td>
          <td className="py-3 pr-3 tabular-nums">
            {countLabel(today?.wins, '')}
            <span className="block text-xs text-slate-500 dark:text-slate-400">
              누적 {countLabel(cumulative?.wins, '')}
            </span>
          </td>
        </>
      )}
      {/* The halt column is the one cell every shape keeps: a tenant that
          cannot order still records what the kernel refused. */}
      <td className="py-3">{row.error == null ? <HaltCell halt={row.halt} /> : null}</td>
    </tr>
  );
}

/**
 * The day's realized total — stocks only, and only when every figure is known.
 *
 * A decision-only tenant is not in it (there is nothing to add), and neither
 * is a hypothetical figure: the three assumptions behind one all push it the
 * same flattering way, so a total mixing them would overstate the day. One
 * unreadable row makes the total «알 수 없음» rather than a sum that silently
 * treats that row as zero.
 */
function TotalsRow({ rows }: { rows: TosSymbolRow[] }) {
  if (rows.length === 0) return null;
  const figures = rows.map((row) => pnlFigure(row.pnl?.today?.pnl_krw));
  const known = figures.every((figure) => figure !== null);
  const total = known ? figures.reduce((sum, figure) => sum + (figure?.amount ?? 0), 0) : null;
  const trips = rows.map((row) => row.pnl?.today?.closed_round_trips);
  const wins = rows.map((row) => row.pnl?.today?.wins);
  const sum = (values: (number | null | undefined)[]) =>
    values.every((value) => value != null)
      ? (values as number[]).reduce((a, b) => a + b, 0)
      : null;
  return (
    <tr className="border-t-2 border-slate-300 font-medium dark:border-slate-600">
      <th scope="row" className="py-3 pr-3 text-left">
        합계
        <span className="block text-xs font-normal text-slate-500 dark:text-slate-400">
          주식 tenant {rows.length}개
        </span>
      </th>
      <td className="py-3 pr-3 text-xs text-slate-500 dark:text-slate-400" colSpan={4}>
        판단 전용 tenant 와 가상 손익은 합계에 들어가지 않습니다.
      </td>
      <td className="py-3 pr-3">
        <Money krw={total == null ? null : String(total)} />
      </td>
      <td className="py-3 pr-3 text-xs text-slate-500 dark:text-slate-400">—</td>
      <td className="py-3 pr-3 tabular-nums">{countLabel(sum(trips))}</td>
      <td className="py-3 pr-3 tabular-nums">{countLabel(sum(wins), '')}</td>
      <td className="py-3" />
    </tr>
  );
}

/** The rows that carry at least one unaccounted order attempt. */
function unresolvedRows(document: { symbols?: TosSymbolRow[] | null }): TosSymbolRow[] {
  return (document.symbols ?? []).filter(
    (row) => (row.pnl?.unresolved?.attempts ?? []).length > 0,
  );
}

/** One order the FIFO could not account for, in the sentence `perf` prints. */
function UnresolvedItem({ attempt }: { attempt: TosSymbolUnresolvedAttempt }) {
  const parts = [
    attempt.side === 'BUY' ? '매수' : attempt.side === 'SELL' ? '매도' : (attempt.side ?? '방향 모름'),
    quantityLabel(attempt.quantity, '주'),
    attempt.order_price_krw == null
      ? '지정가 모름'
      : `지정가 ${Number(attempt.order_price_krw).toLocaleString('ko-KR')}원`,
    attempt.status_label ?? attempt.status ?? '상태 모름',
  ];
  return (
    <li className="text-sm">
      <span className="font-medium">{parts.join(' · ')}</span>
      {attempt.reason ? (
        <span className="block text-xs text-slate-600 dark:text-slate-300">{attempt.reason}</span>
      ) : null}
      {attempt.observation ? (
        <span className="block text-xs text-slate-500 dark:text-slate-400">
          브로커 확인: {attempt.observation}
        </span>
      ) : null}
      {attempt.trading_date ? (
        <span className="block text-xs text-slate-500 dark:text-slate-400">
          거래일 {attempt.trading_date}
        </span>
      ) : null}
    </li>
  );
}

/**
 * «무엇을 사고팔았나» — today's fills and what TOS's own ledger still holds.
 *
 * One row per stock tenant, from a document produced on the host by
 * `sts tos export-symbols` and read by the Control Plane purely as a file —
 * this panel never reaches the kernel, the session stores, or a broker, and
 * nothing here can issue a command.
 *
 * 보유 is labelled «TOS 기준» on purpose: it is the FIFO open lot from TOS's own
 * evidence, not an account balance. The web tier never calls KIS.
 *
 * The PnL columns are the exporter's own figures (`tools/tos_cp3/perf.py`),
 * never re-derived here, and three rules hold across every one of them: an
 * absent figure is «알 수 없음» and never 0; a decision-only tenant has no PnL
 * cell at all rather than a row of zeros; and the totals row sums the stock
 * tenants only — a hypothetical figure is never added to a realized one.
 */
export default function SymbolsPanel({ read }: { read: SymbolsRead }) {
  const { state, document, response, authError } = read;
  const today = isTodaysDocument(document);
  // A document from an earlier day is not an error — the exporter runs at session
  // end — but reading it as today's trading would be. Say so where the rows are.
  const warning = state !== 'ready' && state !== 'loading';

  return (
    <section
      aria-label="거래 현황"
      className="min-w-0 space-y-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="min-w-0">
        <h2 className="font-semibold">거래 현황</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          무엇을 사고팔았나 — 종목마다 그날의 매수 · 매도 체결, TOS 원장이 아는 보유, 실현 손익과
          누적, 그리고 마지막 차단 사유를 봅니다.
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
          {document?.date ? `기준일 ${document.date}` : '기준일 알 수 없음'}
          {document?.generated_kst ? ` · 내보낸 시각 ${document.generated_kst}` : ''}
          {response?.age_seconds != null ? ` · ${ageLabel(response.age_seconds)}` : ''}
        </p>
      </div>

      {document && today === false && (
        <p
          role="alert"
          className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
        >
          기준일 {document.date} — 오늘(KST)의 기록이 아닙니다. 아래 값을 오늘의 거래로 읽지 마세요.
        </p>
      )}

      {document && (
        <div className="min-w-0 overflow-x-auto">
          <table className="w-full min-w-[64rem] text-left text-sm">
            <caption className="sr-only">
              종목별 오늘 매수 · 매도 · 보유(TOS 기준) · 실현 손익 · 누적 · 왕복 · 승 · 마지막 차단
              사유
            </caption>
            <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
              <tr>
                <th scope="col" className="py-2 pr-3">종목</th>
                <th scope="col" className="py-2 pr-3">세션</th>
                <th scope="col" className="py-2 pr-3">오늘 매수</th>
                <th scope="col" className="py-2 pr-3">오늘 매도</th>
                {/* 「TOS 기준」 is a claim about the source of the number, so
                    the header follows the document's own basis: a future basis
                    names itself instead of being read as TOS's ledger. */}
                <th scope="col" className="py-2 pr-3">
                  {document.holding_basis === TOS_LEDGER_HOLDING_BASIS ? (
                    <Term name={TOS_LEDGER_HOLDING_BASIS}>보유 (TOS 기준)</Term>
                  ) : (
                    `보유 (${document.holding_basis ?? '기준 모름'})`
                  )}
                </th>
                <th scope="col" className="py-2 pr-3">
                  오늘 <Term name="realized_pnl">실현 손익</Term>
                </th>
                <th scope="col" className="py-2 pr-3">누적</th>
                <th scope="col" className="py-2 pr-3">
                  <Term name="round_trip">왕복</Term>
                </th>
                <th scope="col" className="py-2 pr-3">승</th>
                <th scope="col" className="py-2">마지막 차단 사유</th>
              </tr>
            </thead>
            <tbody>
              {(document.symbols ?? []).map((row, index) => (
                <SymbolRowCells key={row.tree_id ?? row.symbol ?? index} row={row} />
              ))}
              <TotalsRow rows={tradingRows(document)} />
            </tbody>
          </table>
          {(document.symbols ?? []).length === 0 && (
            <p className="py-3 text-sm text-slate-500 dark:text-slate-400">
              선언된 종목 tenant 가 없습니다.
            </p>
          )}
        </div>
      )}

      {document && unresolvedRows(document).length > 0 && (
        <div className="min-w-0 space-y-2 rounded-lg border border-amber-300 p-3 dark:border-amber-800">
          <h3 className="text-sm font-semibold">
            <Term name="unresolved_order">미해결 주문</Term>
          </h3>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            손익 집계 밖입니다 — 체결로 확정되지 않았으므로 위의 손익에 들어 있지 않습니다.
          </p>
          {unresolvedRows(document).map((row) => (
            <div key={row.tree_id ?? row.symbol}>
              <p className="text-sm font-medium">{row.symbol ?? '알 수 없음'}</p>
              <ul className="ml-4 list-disc space-y-1">
                {(row.pnl?.unresolved?.attempts ?? []).map((attempt, index) => (
                  <UnresolvedItem key={attempt.broker_execution_id ?? index} attempt={attempt} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <AsOf>
        선물 tenant 는 판단만 기록하므로 체결도 보유도 손익도 없습니다 — 그 결과는 ③ 의 가상
        손익(체결 가정)으로만 보고, 위 합계에 더하지 않습니다. 보유는 브로커 잔고 조회가 아니라 TOS
        증거에서 아직 닫히지 않은 수량이며, 체결 시각은 브로커 체결 시각이 아니라 그 주문을 낸 결정
        봉의 시각입니다. 손익은 수수료·세금 전이고, 왕복과 승은 FIFO 로 닫힌 lot 조각마다 셉니다.
      </AsOf>
    </section>
  );
}
