import { apiClient } from './client';

// Wire contract: services/dashboard/routes/tos_symbols.py. Usage plan
// docs/plans/2026-11-19-tos-usage-plan.md §5 «종목별 운영 화면».
//
// Every leaf is optional and nullable because the exporter's own sources report
// "no source == null" and this reader must not turn absence into a fact. The
// document deliberately carries NO filesystem path: the exporter emits none and
// reduces even a leaf-read failure to an exception type name, because this body
// reaches a browser that holds the dashboard API key in its bundle.
//
// Nothing here is a broker read. `holding` is what TOS's own evidence still has
// open (FIFO lots, `holding_basis`), which is why the panel labels it «TOS 기준»
// rather than «잔고».

/** The document version this reader understands (export_symbols.SYMBOLS_SCHEMA_VERSION). */
export const SUPPORTED_SYMBOLS_SCHEMA_VERSION = 1;

/** The only holding basis this page knows how to label. */
export const TOS_LEDGER_HOLDING_BASIS = 'TOS_LEDGER_FIFO_OPEN_LOTS';

/** The only fill-time basis this page knows how to label. */
export const ORDER_BAR_TIME_BASIS = 'ORDER_BAR';

export interface TosSymbolFill {
  quantity?: string | null;
  order_price_krw?: string | null;
  execution_price_krw?: string | null;
  price_basis?: string | null;
  broker_execution_id?: string | null;
  /**
   * KST `HH:MM` of the bar whose decision produced the order — NOT a broker fill
   * clock, which the evidence does not carry. `time_basis` names that, and is
   * null exactly when this is.
   */
  time_kst?: string | null;
  time_basis?: string | null;
}

export interface TosSymbolSide {
  fills?: number | null;
  quantity?: string | null;
  last?: TosSymbolFill | null;
}

export interface TosSymbolHolding {
  quantity?: string | null;
  lots?: number | null;
  basis?: string | null;
}

export interface TosSymbolHaltReason {
  reason?: string | null;
  step?: string | null;
  time_kst?: string | null;
}

export interface TosSymbolHalt {
  error?: string | null;
  last_flow?: TosSymbolHaltReason | null;
  last_withheld?: TosSymbolHaltReason | null;
  flow_counts?: Record<string, number> | null;
}

export interface TosSymbolSession {
  name?: string | null;
  /** `null` means no session ran today — not "unknown status of a session". */
  status?: string | null;
  boot_at?: string | null;
  end_at?: string | null;
  run_rc?: number | null;
}

export interface TosSymbolRow {
  symbol?: string | null;
  tree_id?: string | null;
  session?: TosSymbolSession | null;
  buy?: TosSymbolSide | null;
  sell?: TosSymbolSide | null;
  holding?: TosSymbolHolding | null;
  halt?: TosSymbolHalt | null;
  ticks?: number | null;
  error?: string | null;
}

export interface TosSymbolsDocument {
  schema_version: number;
  /** The KST day these rows describe. Compared against the viewer's own today. */
  date?: string | null;
  generated_kst?: string | null;
  holding_basis?: string | null;
  symbols?: TosSymbolRow[] | null;
}

export interface TosSymbolsResponse {
  available: boolean;
  reason: string | null;
  age_seconds: number | null;
  document: TosSymbolsDocument | null;
}

export type SymbolsState =
  | 'loading' | 'error' | 'missing' | 'unreadable' | 'invalid' | 'unsupported' | 'unknown' | 'ready';

/**
 * The one acceptance predicate for a symbols document.
 *
 * The banner and the table must never disagree about what counts as a usable
 * document — two copies of the same condition means raising the supported
 * version in one place silently blanks or silently renders the other.
 */
export function isAcceptedSymbolsDocument(
  document: TosSymbolsDocument | null | undefined,
): document is TosSymbolsDocument {
  if (!document) return false;
  if (document.schema_version !== SUPPORTED_SYMBOLS_SCHEMA_VERSION) return false;
  return Array.isArray(document.symbols);
}

/**
 * Map one response onto a banner state.
 *
 * Prefix matching, because the shared fixture
 * (tests/fixtures/tos/symbols-reasons.json) declares these as prefixes and the
 * Python side only guarantees each reason *starts with* one. A prefix added
 * there without a branch here fails the UI job rather than landing as 'unknown'.
 */
export function symbolsState(
  response: TosSymbolsResponse | undefined,
  connectionFailed: boolean,
): SymbolsState {
  if (connectionFailed) return 'error';
  if (!response) return 'loading';
  if (!response.available) {
    if (response.reason?.startsWith('symbols document absent')) return 'missing';
    // Not a data-format problem: the file could not be opened at all
    // (permissions, uid mismatch, a directory in its place). Sending the
    // operator to look at the exporter's output would be the wrong instruction.
    if (response.reason?.startsWith('cannot read symbols document')) return 'unreadable';
    if (response.reason?.startsWith('unsupported schema_version')) return 'unsupported';
    if (response.reason?.startsWith('invalid json') || response.reason?.startsWith('schema mismatch')) return 'invalid';
    return 'unknown';
  }
  return isAcceptedSymbolsDocument(response.document) ? 'ready' : 'invalid';
}

/**
 * Today in KST, as `YYYY-MM-DD`.
 *
 * The viewer's own clock and timezone are irrelevant: trading days here are KST
 * (CLAUDE.md, "Timezone"), so a laptop in another zone must not make yesterday's
 * export look current, nor today's look stale.
 */
export function kstToday(now: Date = new Date()): string {
  // en-CA renders ISO-ordered `YYYY-MM-DD`, which is what the document carries.
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(now);
}

/**
 * Whether the document describes the current KST trading day.
 *
 * `null` when the document names no date — unknown stays unknown rather than
 * defaulting to "yes, this is today", which is the reading that would let a
 * stopped exporter pass for live trading.
 */
export function isTodaysDocument(
  document: TosSymbolsDocument | null | undefined,
  now: Date = new Date(),
): boolean | null {
  if (!document?.date) return null;
  return document.date === kstToday(now);
}

/** A row's session state as the page words it — `null` status means none ran. */
export type SessionPhase = 'running' | 'settled' | 'none' | 'unknown';

export function sessionPhase(session: TosSymbolSession | null | undefined): SessionPhase {
  const status = session?.status;
  if (status == null) return 'none';
  if (status === 'RUNNING' || status === 'PRE-BOOT') return 'running';
  // ENDED is the only clean settle; FAILED / ABORT / LOST / NOT-BOOTED all mean
  // the session stopped in a way the operator should look at, so they are not
  // folded into "ended" — the page shows the raw status beside the phase.
  if (status === 'ENDED') return 'settled';
  return 'unknown';
}

export const tosSymbolsApi = {
  getSymbolsToday: async () => {
    const { data } = await apiClient.get<TosSymbolsResponse>('/api/tos/symbols/today');
    return data;
  },
};
