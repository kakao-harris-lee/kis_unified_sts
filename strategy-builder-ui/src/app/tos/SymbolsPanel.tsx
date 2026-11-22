"use client";

import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import config from '@/config/tos-control-plane.json';
import {
  ORDER_BAR_TIME_BASIS,
  TOS_LEDGER_HOLDING_BASIS,
  isAcceptedSymbolsDocument,
  isTodaysDocument,
  sessionPhase,
  symbolsState,
  tosSymbolsApi,
  type SessionPhase,
  type SymbolsState,
  type TosSymbolFill,
  type TosSymbolHalt,
  type TosSymbolHolding,
  type TosSymbolRow,
  type TosSymbolSession,
  type TosSymbolSide,
} from '@/lib/dashboard/tosSymbols';

const labels: Record<SymbolsState, string> = {
  loading: '종목 현황을 불러오는 중',
  error: '종목 현황 조회 연결 오류',
  missing: '아직 종목 현황이 내보내지지 않았습니다',
  unreadable: '종목 현황 파일을 열지 못했습니다',
  invalid: '종목 현황 형식 오류',
  unsupported: '지원하지 않는 종목 현황 버전',
  unknown: '종목 현황 확인 불가',
  ready: '종목 현황을 조회했습니다',
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

const phaseStyles: Record<SessionPhase, string> = {
  running: 'border-emerald-300 text-emerald-800 dark:border-emerald-800 dark:text-emerald-200',
  settled: 'border-slate-300 text-slate-700 dark:border-slate-700 dark:text-slate-300',
  none: 'border-slate-300 text-slate-500 dark:border-slate-700 dark:text-slate-400',
  unknown: 'border-amber-300 text-amber-800 dark:border-amber-800 dark:text-amber-200',
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
          {flow.reason ?? '알 수 없음'}
          {flow.time_kst ? ` · ${flow.time_kst}` : ''}
          {flow.step ? <span className="font-normal text-slate-500 dark:text-slate-400"> · {flow.step}</span> : null}
        </div>
      ) : (
        <div className="text-slate-500 dark:text-slate-400">흐름 정지 없음</div>
      )}
      {withheld && (
        <div className="text-xs text-slate-500 dark:text-slate-400">
          보류 {withheld.reason ?? '알 수 없음'}
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
      <span className={`inline-block rounded-full border px-2 py-0.5 text-xs ${phaseStyles[phase]}`}>
        {phaseLabels[phase]}
        {/* The raw status rides along for every phase but "none": ENDED and
            FAILED are both settled-ish, and the operator needs the difference. */}
        {phase !== 'none' && session?.status ? ` · ${session.status}` : ''}
      </span>
      <div className="text-xs text-slate-500 dark:text-slate-400">
        {session?.boot_at ? `부팅 ${session.boot_at}` : '부팅 기록 없음'}
        {session?.end_at ? ` · 종료 ${session.end_at}` : ''}
        {session?.run_rc != null ? ` · rc=${session.run_rc}` : ''}
      </div>
      <div className="text-xs text-slate-500 dark:text-slate-400">틱 {count(ticks)}</div>
    </div>
  );
}

function SymbolRowCells({ row }: { row: TosSymbolRow }) {
  return (
    <tr className="border-t border-slate-200 align-top dark:border-slate-800">
      <th scope="row" className="py-3 pr-3 text-left font-semibold">
        {row.symbol ?? '알 수 없음'}
      </th>
      <td className="py-3 pr-3">
        <SessionCell session={row.session} ticks={row.ticks} />
      </td>
      {row.error != null ? (
        <td className="py-3 pr-3 text-amber-700 dark:text-amber-300" colSpan={4}>
          기록을 읽지 못했습니다 · {row.error}
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
          <td className="py-3">
            <HaltCell halt={row.halt} />
          </td>
        </>
      )}
    </tr>
  );
}

/**
 * Read-only per-symbol operator rows (usage plan §5 «종목별 운영 화면»).
 *
 * One row per stock tenant: today's buys, today's sells, what TOS's own ledger
 * still holds, and the last thing that blocked a bar. The document is produced
 * on the host by `sts tos export-symbols` and read by the Control Plane purely
 * as a file — this panel never reaches the kernel, the session stores, or a
 * broker, and nothing here can issue a command.
 *
 * 보유 is labelled «TOS 기준» on purpose: it is the FIFO open lot from TOS's own
 * evidence, not an account balance. The web tier never calls KIS.
 */
export default function SymbolsPanel() {
  const query = useQuery({
    queryKey: ['tos-symbols-today'],
    queryFn: tosSymbolsApi.getSymbolsToday,
    refetchInterval: config.pollIntervalMs,
    retry: false,
  });

  const response = query.data;
  const state = symbolsState(response, query.isError || query.fetchStatus === 'paused');
  // The same acceptance predicate the banner uses — see isAcceptedSymbolsDocument.
  const document =
    response?.available && isAcceptedSymbolsDocument(response.document)
      ? response.document
      : null;
  const httpStatus = isAxiosError(query.error) ? query.error.response?.status : undefined;
  const authError = httpStatus === 401 || httpStatus === 403;
  const today = isTodaysDocument(document);
  // A document from an earlier day is not an error — the exporter runs at session
  // end — but reading it as today's trading would be. Say so where the rows are.
  const warning = state !== 'ready' && state !== 'loading';

  return (
    <section
      aria-label="종목별 운영 현황"
      className="min-w-0 space-y-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="min-w-0">
        <h2 className="font-semibold">종목별 운영 현황 · 읽기 전용</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          종목마다 그날의 매수 · 매도 체결, TOS 원장이 아는 보유, 마지막 차단 사유를 봅니다.
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
          {response?.age_seconds != null ? ` · 내보낸 뒤 ${Math.floor(response.age_seconds)}초` : ''}
        </p>
      </div>

      {document && today === false && (
        <p role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
          기준일 {document.date} — 오늘(KST)의 기록이 아닙니다. 아래 값을 오늘의 거래로 읽지 마세요.
        </p>
      )}

      {document && (
        <div className="min-w-0 overflow-x-auto">
          <table className="w-full min-w-[46rem] text-left text-sm">
            <caption className="sr-only">
              종목별 오늘 매수 · 매도 · 보유(TOS 기준) · 마지막 차단 사유
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
                  보유 (
                  {document.holding_basis === TOS_LEDGER_HOLDING_BASIS
                    ? 'TOS 기준'
                    : (document.holding_basis ?? '기준 모름')}
                  )
                </th>
                <th scope="col" className="py-2">마지막 차단 사유</th>
              </tr>
            </thead>
            <tbody>
              {(document.symbols ?? []).map((row, index) => (
                <SymbolRowCells key={row.tree_id ?? row.symbol ?? index} row={row} />
              ))}
            </tbody>
          </table>
          {(document.symbols ?? []).length === 0 && (
            <p className="py-3 text-sm text-slate-500 dark:text-slate-400">
              선언된 종목 tenant 가 없습니다.
            </p>
          )}
        </div>
      )}

      <p className="text-xs text-slate-500 dark:text-slate-400">
        보유는 브로커 잔고 조회가 아니라 TOS 증거에서 아직 닫히지 않은 수량입니다. 체결 시각은
        브로커 체결 시각이 아니라 그 주문을 낸 결정 봉의 시각입니다.
      </p>
    </section>
  );
}
