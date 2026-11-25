import { apiClient } from './client';
import displayConfig from '@/config/tos-control-plane.json';

// Wire contract: services/dashboard/routes/tos_bars.py. Roadmap
// docs/plans/2026-11-11-tos-platform-roadmap.md §P1, second item.
//
// Every leaf is optional and nullable because the producer's own convention is
// "no source == null" and this reader must not turn absence into a fact. The
// document deliberately carries NO filesystem path: the route drops `data_dir`,
// `strategy.path` and `bindings.path` before the body is built, because this
// body reaches a browser that holds the dashboard API key in its bundle.

/** The sentinel the panel opens on — the most recently exported session. */
export const LATEST_SESSION = 'latest';

/** The document version this reader understands (export_bars.BARS_SCHEMA_VERSION). */
export const SUPPORTED_BARS_SCHEMA_VERSION = 1;

export interface TosBarsCompare {
  index?: number | null;
  expression?: string | null;
  left_value?: string | null;
  right_value?: string | null;
  passed?: boolean | null;
}

export interface TosBarsRule {
  label?: string | null;
  rule_id?: string | null;
  decision_kind?: string | null;
  fired?: boolean | null;
  compares?: TosBarsCompare[] | null;
}

export interface TosBarsEvidence {
  joined?: boolean | null;
  unjoined_reason?: string | null;
  event_id?: string | null;
  snapshot_id?: string | null;
  outcome_type?: string | null;
  outcome_halt_reason?: string | null;
  consumed_halt_reason?: string | null;
  consumed_halt_step?: string | null;
  withheld_reason?: string | null;
  halt_step?: string | null;
  halt_reason?: string | null;
  halt_detail?: string | null;
  value_view?: Record<string, boolean | number | string> | null;
  value_view_refusal?: string | null;
}

export interface TosBarsBar {
  raw_event_id?: string | null;
  as_of_ms?: number | null;
  time_kst?: string | null;
  time_source?: string | null;
  fields?: Record<string, boolean | number | string> | null;
  env_values?: Record<string, boolean | number | string> | null;
  evaluation?: string | null;
  counted?: boolean | null;
  /** Four fixed positions: V=view≠journal D=decision≠engine W=withheld U=journal-substituted. */
  flags?: string | null;
  view_diff?: Record<string, { value_view?: string | null; journal?: string | null }> | null;
  engine_shape?: string | null;
  decision_disagrees?: boolean | null;
  decision_rule_id?: string | null;
  decision_kind?: string | null;
  rules?: TosBarsRule[] | null;
  evidence?: TosBarsEvidence | null;
}

export interface TosBarsSummaryCompare {
  index?: number | null;
  expression?: string | null;
  failed_bars?: number | null;
  bars?: number | null;
  failed_pct?: number | null;
}

export interface TosBarsSummaryRule {
  label?: string | null;
  rule_id?: string | null;
  fired_bars?: number | null;
  bars?: number | null;
  fired_pct?: number | null;
  compares?: TosBarsSummaryCompare[] | null;
}

export interface TosBarsSummary {
  bars?: number | null;
  counted_bars?: number | null;
  withheld_bars?: number | null;
  substituted_bars?: number | null;
  view_diff_bars?: number | null;
  view_diff_fields?: Record<string, number> | null;
  disagreement_bars?: number | null;
  not_comparable_bars?: number | null;
  rules?: TosBarsSummaryRule[] | null;
  decisions?: Record<string, number> | null;
  evidence_outcomes?: Record<string, number> | null;
  evidence_halts?: Record<string, number> | null;
  unjoined?: Record<string, number> | null;
  value_view_refused?: Record<string, number> | null;
}

export interface TosBarsDocument {
  schema_version: number;
  session?: string | null;
  instrument?: string | null;
  strategy?: { sha256?: string | null } | null;
  bindings?: { values?: Record<string, boolean | number | string> | null } | null;
  window?: { from?: string | null; to?: string | null } | null;
  default?: { rule_id?: string | null; decision_kind?: string | null } | null;
  bars?: TosBarsBar[] | null;
  summary?: TosBarsSummary | null;
}

export interface TosBarsResponse {
  available: boolean;
  reason: string | null;
  age_seconds: number | null;
  session: string | null;
  document: TosBarsDocument | null;
}

export type BarsState =
  | 'loading' | 'error' | 'missing' | 'unreadable' | 'invalid' | 'unsupported' | 'bad-request' | 'unknown' | 'ready';

/**
 * The one acceptance predicate for a bars document.
 *
 * The banner and the panel body must never disagree about what counts as a
 * usable document — two copies of the same condition means raising the
 * supported version in one place silently blanks or silently renders the other.
 */
export function isAcceptedBarsDocument(
  document: TosBarsDocument | null | undefined,
): document is TosBarsDocument {
  if (!document) return false;
  if (document.schema_version !== SUPPORTED_BARS_SCHEMA_VERSION) return false;
  return Array.isArray(document.bars);
}

/**
 * Map one response onto a banner state.
 *
 * Prefix matching, because the shared fixture
 * (tests/fixtures/tos/bars-reasons.json) declares these as prefixes and the
 * Python side only guarantees each reason *starts with* one. A prefix added
 * there without a branch here fails the UI job rather than landing as
 * 'unknown'.
 */
export function barsState(
  response: TosBarsResponse | undefined,
  connectionFailed: boolean,
): BarsState {
  if (connectionFailed) return 'error';
  if (!response) return 'loading';
  if (!response.available) {
    if (response.reason?.startsWith('bars document absent')) return 'missing';
    // Not a data-format problem: the file could not be opened at all
    // (permissions, uid mismatch, a directory in its place). Sending the
    // operator to look at the exporter's output would be the wrong instruction.
    if (response.reason?.startsWith('cannot read bars document')) return 'unreadable';
    if (response.reason?.startsWith('unsupported schema_version')) return 'unsupported';
    if (response.reason?.startsWith('invalid session id')) return 'bad-request';
    if (response.reason?.startsWith('invalid json') || response.reason?.startsWith('schema mismatch')) return 'invalid';
    return 'unknown';
  }
  return isAcceptedBarsDocument(response.document) ? 'ready' : 'invalid';
}

/** The flag letters, in the document's own fixed positions. */
export const BAR_FLAGS = ['V', 'D', 'W', 'U'] as const;
export type BarFlag = (typeof BAR_FLAGS)[number];

/** Whether `bar` carries `flag`, by position rather than by substring search. */
export function hasFlag(bar: TosBarsBar, flag: BarFlag): boolean {
  const index = BAR_FLAGS.indexOf(flag);
  return bar.flags?.[index] === flag;
}

/**
 * A bar's numeric field, preferring what the engine ACTUALLY evaluated.
 *
 * `env_values` is the engine's own value view on a counted bar; `fields` is the
 * producer's journal line. Where they differ the view is the right answer (that
 * is what the `V` marker is about), so the chart reads the view first and falls
 * back to the journal only when there is no view — a withheld bar, or one whose
 * chain broke.
 */
export function barValue(bar: TosBarsBar, key: string): number | null {
  for (const source of [bar.env_values, bar.fields]) {
    const raw = source?.[key];
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  }
  return null;
}

// ---------------------------------------------------------------------------
// The session listing — GET /api/tos/sessions, what the picker offers.
// ---------------------------------------------------------------------------

/**
 * One exported session, as the ROUTE derived it from the document's file name.
 *
 * Nothing here is read from the document: a megabyte apiece, per page load, for
 * one string each. So a field the name does not carry arrives null and this
 * module must not invent it — except for the one case config answers below.
 */
export interface TosSessionEntry {
  session: string;
  /** `YYYY-MM-DD`, or null when the name's tail is eight digits that are not a date. */
  date: string | null;
  kind: 'futures' | 'stock' | 'other';
  /** `LONG`/`SHORT` on a futures session. */
  direction: string | null;
  /** The symbol when the NAME carries it (`stock-000660-r1-…`). */
  instrument: string | null;
  /** Cron is run 1; an operator restart on the same day is run 2. */
  run: number | null;
  age_seconds: number | null;
}

export interface TosSessionsResponse {
  available: boolean;
  reason: string | null;
  sessions: TosSessionEntry[];
  /** True when the route's cap dropped older sessions. The newest are kept. */
  truncated: boolean;
}

/**
 * The symbol of the stock tenant whose session name predates the per-symbol
 * convention: `stock-r<N>-<날짜>`, where every tenant since is
 * `stock-<symbol>-r<N>-<날짜>`.
 *
 * **This value mirrors `STOCK_LEGACY_SYMBOL=005930` in
 * `tools/tos_cp3/runners/cp3_tenant_daily.sh`** — the runner that composes the
 * names in the first place. Its line 199 is the whole rule:
 * `if [ "$SYMBOL" = "$STOCK_LEGACY_SYMBOL" ]; then lc=stock; else lc=stock-$SYMBOL; fi`.
 * So if that variable is ever repointed at another symbol, this label follows
 * it or starts lying about which tenant the operator is looking at. The two
 * cannot be held together by an import (the runner is host-side shell, this is
 * a browser bundle), which is why the dependency is written here instead.
 *
 * The value is config (src/config/tos-control-plane.json — JSON takes no
 * comment, hence this note at the read) rather than a literal in a branch, per
 * the repo rule that symbols belong in configuration. It lives on THIS side
 * rather than in the route because it is a display label, not a fact the route
 * established — the route refuses to claim an instrument the file name does
 * not carry.
 */
export const LEGACY_STOCK_INSTRUMENT = displayConfig.legacyStockInstrument;

/** `2026-11-25` → `11-25`; anything else is passed through unchanged. */
export function sessionDayLabel(date: string | null): string {
  return date && date.length === 10 ? date.slice(5) : (date ?? '날짜 없음');
}

/**
 * What this session IS, in one Korean phrase: `선물 LONG`, `주식 005930`.
 *
 * The run is shown only when it is not cron's: every session would otherwise
 * carry a `· r1` that distinguishes nothing, and the one case the operator
 * needs to see — a restart beside cron's own run on the same day — would be
 * that much harder to spot.
 */
export function sessionKindLabel(entry: TosSessionEntry): string {
  if (entry.kind === 'futures') {
    return entry.direction ? `선물 ${entry.direction}` : '선물';
  }
  if (entry.kind === 'stock') {
    const instrument = entry.instrument ?? LEGACY_STOCK_INSTRUMENT;
    return entry.run != null && entry.run !== 1
      ? `주식 ${instrument} · r${entry.run}`
      : `주식 ${instrument}`;
  }
  // A shape this reader will not claim to recognise: say the name itself
  // rather than a label that pretends to know more than the route does.
  return entry.session;
}

/** The option's text: `11-25 · 주식 005930`. */
export function sessionOptionLabel(entry: TosSessionEntry): string {
  const kind = sessionKindLabel(entry);
  return entry.date ? `${sessionDayLabel(entry.date)} · ${kind}` : kind;
}

export interface TosSessionGroup {
  date: string | null;
  label: string;
  sessions: TosSessionEntry[];
}

/**
 * The listing as `<optgroup>`s, one per trading day.
 *
 * Order is the route's own (newest day first, stable inside a day) — grouping
 * must not re-sort, or the picker and the API would disagree about which
 * session is the most recent while `latest` still resolves by export time.
 */
export function groupSessionsByDate(sessions: TosSessionEntry[]): TosSessionGroup[] {
  const groups = new Map<string, TosSessionGroup>();
  for (const entry of sessions) {
    const key = entry.date ?? '';
    const group = groups.get(key);
    if (group) {
      group.sessions.push(entry);
    } else {
      groups.set(key, {
        date: entry.date,
        label: entry.date ?? '날짜 없음',
        sessions: [entry],
      });
    }
  }
  return [...groups.values()];
}

export const tosBarsApi = {
  getBars: async (sessionId: string) => {
    const { data } = await apiClient.get<TosBarsResponse>(
      `/api/tos/sessions/${encodeURIComponent(sessionId)}/bars`,
    );
    return data;
  },
  listSessions: async () => {
    const { data } = await apiClient.get<TosSessionsResponse>('/api/tos/sessions');
    return data;
  },
};
