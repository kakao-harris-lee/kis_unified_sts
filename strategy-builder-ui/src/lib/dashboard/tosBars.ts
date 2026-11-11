import { apiClient } from './client';

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

export const tosBarsApi = {
  getBars: async (sessionId: string) => {
    const { data } = await apiClient.get<TosBarsResponse>(
      `/api/tos/sessions/${encodeURIComponent(sessionId)}/bars`,
    );
    return data;
  },
};
