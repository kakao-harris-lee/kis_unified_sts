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

/**
 * What one authored rule means, in the words its author wrote.
 *
 * `rationale` is the strategy YAML's own sentence — the page shows it instead
 * of the bare `R1-ENTRY-LONG`. `probe` says the rule is an order-path exercise
 * rather than a strategy signal, and it is NOT parsed out of that sentence: it
 * comes from an operator-side map (config/tos_bars_explain.yaml), because the
 * strategy DSL forbids extra keys and the strategy's digest is a replay input.
 */
export interface TosBarsExplainRule {
  label?: string | null;
  rule_id?: string | null;
  decision_kind?: string | null;
  rationale?: string | null;
  target_rationale?: string | null;
  probe?: boolean | null;
  /** The published field names this rule compares, in the order it reads them. */
  fields?: string[] | null;
  /** The binding keys it compares against; their values are in `bindings`. */
  bindings?: string[] | null;
}

/** One field's definition from the tenant's `fields.yaml`. */
export interface TosBarsExplainField {
  /** The catalog's internal name (`z` for the published `z_x1000`). */
  field?: string | null;
  op?: string | null;
  inputs?: string[] | null;
  /**
   * Any JSON value, deliberately: `fields.yaml` is authored content and a
   * future operation may take a null (`when_missing: null`), a list, or a
   * nested mapping. A narrow type here would make one new parameter shape fail
   * the whole document and take the bars down with it.
   */
  params?: Record<string, unknown> | null;
  scale?: Record<string, unknown> | null;
  published_as?: string | null;
  /** False when the catalog did not define this name — not an invented op. */
  known?: boolean | null;
}

export interface TosBarsExplain {
  schema?: string | null;
  rules?: TosBarsExplainRule[] | null;
  default?: TosBarsExplainRule | null;
  /** Keyed by the name the rules reference, plus every field those stand on. */
  fields?: Record<string, TosBarsExplainField> | null;
  probe_basis?: string | null;
}

/** One would-have-been trade. Never a fill, and never a realized figure. */
export interface TosHypotheticalTrade {
  entry_time_kst?: string | null;
  entry_rule_id?: string | null;
  entry_price_points?: string | null;
  exit_time_kst?: string | null;
  /** Null on a forced close: no rule said to exit, the session just ended. */
  exit_rule_id?: string | null;
  exit_price_points?: string | null;
  points?: string | null;
  hypothetical_pnl_krw?: string | null;
  forced_close?: boolean | null;
  forced_close_reason?: string | null;
}

export interface TosHypotheticalTotals {
  trades?: number | null;
  wins?: number | null;
  /**
   * Null — not `'0'` — on a session with no trade at all. A zero renders as
   * "±0 today", which is a different claim from "no signal fired".
   */
  points?: string | null;
  /** Deliberately not named `pnl_krw` — it must never be summed with one. */
  hypothetical_pnl_krw?: string | null;
  forced_closes?: number | null;
}

/** A decision bar whose close could not be read, so it is outside the total. */
export interface TosHypotheticalDecision {
  time_kst?: string | null;
  decision_kind?: string | null;
  rule_id?: string | null;
}

/** Reasons a decision bar was deliberately left out of the total. */
export const SKIP_NOT_ENGINE_COUNTED = 'NOT_ENGINE_COUNTED';
export const SKIP_ENGINE_DISAGREES = 'ENGINE_DISAGREES';
export const SKIP_PROBE_ENTRY = 'PROBE_ENTRY';

/**
 * A decision bar left out of the total on purpose, and why.
 *
 * The first two reasons mean the bar's `decision_kind` was re-derived by the
 * inspection rather than made by the engine; `PROBE_ENTRY` means the rule is an
 * order-path exercise, not a signal. Counting any of them would attribute to
 * the strategy something it did not do.
 */
export interface TosHypotheticalSkipped extends TosHypotheticalDecision {
  reason?: string | null;
}

/**
 * What a decision-only tenant's decisions WOULD have earned, had they filled.
 *
 * Present only for the futures tenants, which decide but never order (operator
 * decision 2026-11-05). The page labels every one of these numbers «가상
 * 손익(체결 가정)» and never adds them to a realized PnL: the three assumptions
 * (a guaranteed fill, no fees, no slippage) all push the figure the same,
 * flattering way.
 */
export interface TosBarsHypotheticalPnl {
  hypothetical?: boolean | null;
  direction?: string | null;
  instrument?: string | null;
  contract?: string | null;
  multiplier_krw_per_point?: number | null;
  price_field?: string | null;
  price_scale?: number | null;
  assumptions?: string[] | null;
  trades?: TosHypotheticalTrade[] | null;
  totals?: TosHypotheticalTotals | null;
  unpriced_decisions?: TosHypotheticalDecision[] | null;
  /**
   * Decision bars deliberately left out, each with its reason — so the page can
   * say what the total excluded instead of implying it counted everything.
   */
  skipped_decisions?: TosHypotheticalSkipped[] | null;
}

export interface TosBarsDocument {
  schema_version: number;
  session?: string | null;
  instrument?: string | null;
  /** `stock`/`futures`, from the tenant tree the session actually ran. */
  market?: string | null;
  /**
   * True on a tenant that decides but never orders. The page must not draw an
   * absent order as "ordered nothing".
   */
  decision_only?: boolean | null;
  strategy?: { sha256?: string | null } | null;
  bindings?: { values?: Record<string, boolean | number | string> | null } | null;
  window?: { from?: string | null; to?: string | null } | null;
  default?: { rule_id?: string | null; decision_kind?: string | null } | null;
  bars?: TosBarsBar[] | null;
  summary?: TosBarsSummary | null;
  explain?: TosBarsExplain | null;
  /** Why there is no explanation. A bars document is still good without one. */
  explain_error?: string | null;
  hypothetical_pnl?: TosBarsHypotheticalPnl | null;
  hypothetical_pnl_error?: string | null;
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

/**
 * One rule's explanation, by the id a bar names.
 *
 * Matched on `rule_id`, never on `label`: `label` is the rule's POSITION in the
 * policy (`R1`, `R2`) while a bar's `decision_rule_id` is the authored id
 * (`R1-ENTRY-LONG`). Two tenants' policies put different rules at the same
 * position, so matching on label would caption a 005380 bar with 005930's
 * sentence — and the whole point of this block is that the caption is true.
 *
 * Also covers the default rule, which fires on most bars and is not in `rules`.
 */
export function ruleExplanation(
  document: TosBarsDocument | null | undefined,
  ruleId: string | null | undefined,
): TosBarsExplainRule | null {
  if (!ruleId) return null;
  const explain = document?.explain;
  if (!explain) return null;
  const found = explain.rules?.find((rule) => rule.rule_id === ruleId);
  if (found) return found;
  return explain.default?.rule_id === ruleId ? explain.default : null;
}

/**
 * One published field's definition, by the name a comparison names it.
 *
 * `explain.fields` is keyed by BOTH the catalog's internal name and the
 * published alias (`z` and `z_x1000` both resolve), so a lookup by the name the
 * rule compared finds it without this side re-deriving the scale suffix.
 */
export function explainField(
  document: TosBarsDocument | null | undefined,
  name: string | null | undefined,
): TosBarsExplainField | null {
  if (!name) return null;
  return document?.explain?.fields?.[name] ?? null;
}

/**
 * A field definition as one short line: `between(mso) · lo=15 · hi=345`.
 *
 * The operation and its inputs are the tenant's own `fields.yaml` words, kept
 * verbatim: translating `ratio_z` into prose here would be this bundle's claim
 * about what the catalog computes, and the sentence beside it (the rule's
 * `rationale`) is already the authored explanation. Null when the document
 * does not define the field, or defines it without an operation — an invented
 * «알 수 없음(…)» line would read as a definition.
 */
export function fieldDefinitionLabel(
  field: TosBarsExplainField | null | undefined,
): string | null {
  if (!field?.op) return null;
  const inputs = (field.inputs ?? []).join(', ');
  const params = Object.entries(field.params ?? {})
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(' · ');
  const head = `${field.op}(${inputs})`;
  return params ? `${head} · ${params}` : head;
}

/**
 * Whether this document carries a hypothetical PnL that may be shown.
 *
 * Guarded on `hypothetical === true` rather than on the block merely existing:
 * a block whose own flag is missing has not asserted what it is, and a page
 * that shows it anyway is one label away from presenting an assumed fill as
 * money. It is never summed with a realized figure — there is no realized
 * figure on a decision-only tenant to sum it with.
 */
export function hasHypotheticalPnl(
  document: TosBarsDocument | null | undefined,
): boolean {
  return document?.decision_only === true && document?.hypothetical_pnl?.hypothetical === true;
}

/**
 * Why a decision-only session has no hypothetical figure, when it says.
 *
 * The exporter writes `hypothetical_pnl_error` and leaves the block out when it
 * cannot price the decisions (an unknown contract multiplier, a missing price
 * field). Rendering nothing at all in that case is the worst of the three
 * possible screens: the operator sees a futures card with no result and cannot
 * tell «it decided nothing» from «it decided and we could not price it». So the
 * page shows the sentence instead of the figure.
 */
export function hypotheticalError(
  document: TosBarsDocument | null | undefined,
): string | null {
  if (document?.decision_only !== true) return null;
  if (hasHypotheticalPnl(document)) return null;
  return document?.hypothetical_pnl_error ?? null;
}

/**
 * How many decision bars the hypothetical total deliberately left out.
 *
 * Skipped (not the engine's, a disagreement, a probe) and unpriced (the close
 * could not be read) together: both mean «there were decisions, they are just
 * not in this number», which is a different screen from «there were none».
 */
export function excludedDecisionCount(
  block: TosBarsHypotheticalPnl | null | undefined,
): number {
  return (block?.skipped_decisions?.length ?? 0) + (block?.unpriced_decisions?.length ?? 0);
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
