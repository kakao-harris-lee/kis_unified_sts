// Reading a bars document the way an operator asks about it: «왜 진입했나 /
// 안 했나», «무엇이 막았나». Pure functions over the DTOs in ./tosBars — no
// React, no I/O — so every claim the page makes about a bar is unit-testable
// without rendering anything.
//
// Two facts shape everything here.
//
// 1. **A strategy condition and a kernel gate are different things.** A rule's
//    comparison being false means the strategy saw no signal. A halt means the
//    strategy DID decide and a stage of the kernel refused to let the order
//    out. Conflating them would let «오늘은 기회가 없었다» and «오늘은 전부
//    막혔다» render identically, so they travel as separate values from here to
//    the screen and are never merged into one «실패» count.
// 2. **Nothing is invented.** Absent is absent: a field with no value yields
//    null and the caller says 「알 수 없음」. A withheld bar was never judged,
//    so it reports neither a passing nor a failing condition.

import {
  type TosBarsBar,
  type TosBarsCompare,
  type TosBarsRule,
  type TosBarsSummary,
  type TosBarsSummaryRule,
} from './tosBars';
import { glossaryKey, glossaryLabel } from './tosGlossary';

/** Rule ids that carry this marker are probes, not strategy signals. */
const PROBE_MARKER = 'PROBE';

/** The comparison operators the DSL emits, with the symbol the page shows. */
const OPERATORS: Record<string, string> = {
  EQ: '=',
  NE: '≠',
  LT: '<',
  LE: '≤',
  GT: '>',
  GE: '≥',
};

// ---------------------------------------------------------------------------
// Units: turning a published field's integer back into the number a human reads
// ---------------------------------------------------------------------------

/**
 * The factor a published name was scaled by, from its own suffix.
 *
 * The tenant's `publish:` block renames each field with the factor it
 * multiplied by (`close` → `close_x100`, `z` → `z_x1000`), so the document is
 * self-describing on this point and the page needs no per-tenant table. A name
 * without a suffix is unscaled.
 */
export function fieldScale(name: string): number {
  const match = /_x(\d+)$/.exec(name);
  if (!match) return 1;
  const factor = Number(match[1]);
  return Number.isFinite(factor) && factor > 0 ? factor : 1;
}

/**
 * A raw document value as the operator reads it.
 *
 * Booleans become 예/아니오 and scaled integers are divided back. Decimals are
 * capped at two: this page is read at a glance, and the third decimal of a z
 * score has never changed an operator's answer. The value a rule was actually
 * decided on is the integer in the document, which stays visible as the raw
 * expression beside every row.
 */
export function formatFieldValue(name: string, raw: string | null | undefined): string | null {
  if (raw == null || raw === '') return null;
  if (raw === 'true') return '예';
  if (raw === 'false') return '아니오';
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return raw;
  const scale = fieldScale(name);
  const digits = scale > 1 ? Math.min(String(scale).length - 1, 2) : 0;
  return (parsed / scale).toLocaleString('ko-KR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

/** A bar's numeric field in human units, or null when the bar has no value. */
export function barDisplayValue(bar: TosBarsBar, key: string): string | null {
  const raw = bar.env_values?.[key] ?? bar.fields?.[key];
  if (raw == null) return null;
  return formatFieldValue(key, String(raw));
}

// ---------------------------------------------------------------------------
// One comparison, as a sentence
// ---------------------------------------------------------------------------

export interface ParsedCompare {
  left: string;
  op: string;
  right: string;
}

/**
 * `"z_x1000 LE config.z_entry_max_x1000"` → its three parts.
 *
 * Null for anything that is not exactly three whitespace-separated tokens: a
 * future DSL shape must fall back to showing the raw expression rather than be
 * mis-parsed into a confident wrong sentence.
 */
export function parseCompare(expression: string | null | undefined): ParsedCompare | null {
  if (!expression) return null;
  const parts = expression.trim().split(/\s+/);
  if (parts.length !== 3) return null;
  const [left, op, right] = parts;
  if (!(op in OPERATORS)) return null;
  return { left, op, right };
}

export interface ConditionRow {
  index: number;
  /** The plain-Korean name of what is tested. */
  name: string;
  /** Glossary key for the term tooltip, or null when the name is raw. */
  termKey: string | null;
  /** The condition in one short phrase, for the formula line. */
  short: string;
  /** What this bar actually had, in human units. */
  actual: string;
  /** The threshold in human units — null when the requirement is a boolean. */
  threshold: string | null;
  passed: boolean | null;
  /** How far this bar was from passing, when both sides are numbers. */
  distance: { amount: string; direction: 'up' | 'down' } | null;
  /** The document's own expression, kept as secondary text. */
  expression: string;
}

function isNumeric(value: string | null | undefined): boolean {
  return value != null && value !== '' && value !== 'true' && value !== 'false' && Number.isFinite(Number(value));
}

/**
 * One comparison as a row of the checklist.
 *
 * The threshold shown is the document's `right_value` — the number the engine
 * actually compared against — not a constant restated in this bundle. A binding
 * the operator changes therefore changes this row, with no UI release.
 */
export function conditionRow(compare: TosBarsCompare, position: number): ConditionRow {
  const expression = compare.expression ?? '';
  const parsed = parseCompare(expression);
  const index = compare.index ?? position + 1;
  const leftName = parsed?.left ?? '';
  const termKey = leftName ? glossaryKey(leftName) : null;
  const name = leftName ? glossaryLabel(leftName) : (expression || '알 수 없음');
  const actual = (leftName ? formatFieldValue(leftName, compare.left_value) : null) ?? '알 수 없음';
  const numeric = isNumeric(compare.left_value) && isNumeric(compare.right_value);
  const symbol = parsed ? OPERATORS[parsed.op] : '';

  if (!parsed || !numeric) {
    // A boolean gate, or a shape this reader will not claim to parse. The
    // requirement is what the right side demands, named through the glossary
    // when it is a config binding rather than a literal.
    const demanded =
      compare.right_value === 'true'
        ? '예'
        : compare.right_value === 'false'
          ? '아니오'
          : (compare.right_value ?? '알 수 없음');
    const rightLabel =
      parsed && parsed.right.startsWith('config.') ? `${glossaryLabel(parsed.right)}(${demanded})` : demanded;
    return {
      index,
      name,
      termKey,
      short: name,
      actual,
      threshold: parsed ? rightLabel : null,
      passed: compare.passed ?? null,
      distance: null,
      expression,
    };
  }

  const left = Number(compare.left_value);
  const right = Number(compare.right_value);
  const scale = fieldScale(leftName);
  const threshold = formatFieldValue(leftName, compare.right_value) ?? '알 수 없음';
  // Only an ordered comparison has a direction to travel. EQ/NE would have to
  // claim 「올라가야」 or 「내려가야」 about a value that merely has to differ, so
  // they report no distance and the row says 「값이 바뀌어야 충족」 instead.
  const ordered = parsed.op === 'LE' || parsed.op === 'LT' || parsed.op === 'GE' || parsed.op === 'GT';
  const needsLower = parsed.op === 'LE' || parsed.op === 'LT';
  const gap = Math.abs(left - right) / scale;
  const distance =
    ordered && compare.passed === false && gap > 0
      ? {
          amount: gap.toLocaleString('ko-KR', { minimumFractionDigits: 0, maximumFractionDigits: 2 }),
          direction: (needsLower ? 'down' : 'up') as 'up' | 'down',
        }
      : null;

  return {
    index,
    name,
    termKey,
    short: `${name} ${symbol} ${threshold}`,
    actual,
    threshold: `${symbol} ${threshold}`,
    passed: compare.passed ?? null,
    distance,
    expression,
  };
}

/** Every comparison of a rule, in the document's own order. */
export function conditionRows(rule: TosBarsRule | null | undefined): ConditionRow[] {
  return (rule?.compares ?? []).map((compare, position) => conditionRow(compare, position));
}

// ---------------------------------------------------------------------------
// Which rule is which
// ---------------------------------------------------------------------------

export interface RuleRoles {
  /** The strategy's entry rule — an ACTION rule that is not a probe. */
  entry: TosBarsRule | null;
  /** The order-path probe, which the strategy YAML states is NOT a signal. */
  probe: TosBarsRule | null;
  /** The rules that close a position. */
  exits: TosBarsRule[];
}

export function isProbeRule(ruleId: string | null | undefined): boolean {
  return ruleId != null && ruleId.includes(PROBE_MARKER);
}

/**
 * Sort a bar's rules into the roles the page talks about.
 *
 * By `decision_kind` and the probe marker in the id, never by position: a
 * tenant may declare its rules in any order, and 005380 already runs a
 * different rule set (RSI/%R) from the Setup D trees.
 */
export function ruleRoles(rules: TosBarsRule[] | null | undefined): RuleRoles {
  const roles: RuleRoles = { entry: null, probe: null, exits: [] };
  for (const rule of rules ?? []) {
    if (isProbeRule(rule.rule_id)) {
      roles.probe ??= rule;
    } else if (rule.decision_kind === 'ACTION') {
      roles.entry ??= rule;
    } else if (rule.decision_kind === 'FLAT') {
      roles.exits.push(rule);
    }
  }
  return roles;
}

export interface EntryProgress {
  passed: number;
  total: number;
  /** The plain-Korean names of the conditions that were false. */
  failing: string[];
  ruleId: string | null;
}

/**
 * How close this bar was to the entry rule — «n/5 충족».
 *
 * Null when the bar carries no entry rule at all, which is what a withheld bar
 * looks like: it was never judged, so it has no score to report.
 */
export function entryProgress(bar: TosBarsBar | null | undefined): EntryProgress | null {
  const entry = ruleRoles(bar?.rules).entry;
  const compares = entry?.compares ?? [];
  if (!entry || compares.length === 0) return null;
  const rows = conditionRows(entry);
  return {
    passed: rows.filter((row) => row.passed === true).length,
    total: rows.length,
    failing: rows.filter((row) => row.passed === false).map((row) => row.name),
    ruleId: entry.rule_id ?? null,
  };
}

/** The published field every tenant uses to say the entry window is open. */
const ENTRY_WINDOW_FIELD = 'entry_window';

/**
 * Whether this bar fell inside the tenant's entry window.
 *
 * `null` when the tenant publishes no such field — unknown stays unknown, and
 * the callers below then treat every judged bar as eligible rather than
 * silently reporting 「해당 봉 없음」 for a tenant whose window they cannot see.
 */
export function entryWindowOpen(bar: TosBarsBar): boolean | null {
  const raw = bar.env_values?.[ENTRY_WINDOW_FIELD] ?? bar.fields?.[ENTRY_WINDOW_FIELD];
  return typeof raw === 'boolean' ? raw : null;
}

export interface ProgressAt {
  progress: EntryProgress;
  timeKst: string | null;
}

function progressAt(bar: TosBarsBar): ProgressAt | null {
  const progress = entryProgress(bar);
  return progress ? { progress, timeKst: bar.time_kst ?? null } : null;
}

/** Every judged bar inside the entry window, in the document's order. */
function inWindowBars(bars: TosBarsBar[] | null | undefined): TosBarsBar[] {
  return (bars ?? []).filter((bar) => bar.counted === true && entryWindowOpen(bar) !== false);
}

/**
 * The closest the day ever came to entering, and when.
 *
 * Not the last bar: after 15:15 every session ends on an EOD bar whose entry
 * window is shut, so «마지막 봉 기준» reports the same 1/5 for every tenant
 * every evening and answers nothing. The question the card asks is «얼마나
 * 가까웠나», which is a maximum over the window, and the earliest bar that
 * reached it is the one reported so the time means "from here on it never got
 * better".
 */
export function bestEntryProgress(bars: TosBarsBar[] | null | undefined): ProgressAt | null {
  let best: ProgressAt | null = null;
  for (const bar of inWindowBars(bars)) {
    const at = progressAt(bar);
    if (!at) continue;
    if (!best || at.progress.passed > best.progress.passed) best = at;
  }
  return best;
}

/** The last judged bar whose entry window was still open. */
export function latestInWindowProgress(bars: TosBarsBar[] | null | undefined): ProgressAt | null {
  const inside = inWindowBars(bars);
  for (let index = inside.length - 1; index >= 0; index -= 1) {
    const at = progressAt(inside[index]);
    if (at) return at;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Gates: what the kernel refused, as distinct from what the strategy decided
// ---------------------------------------------------------------------------

export interface BarGate {
  /** The raw code, which stays on screen as secondary text. */
  reason: string;
  step: string | null;
  /** The plain-Korean name of the gate. */
  label: string;
  /** The evidence's own readable sentence, when it wrote one. */
  detail: string | null;
}

/**
 * The gate that stopped this bar, or null when nothing did.
 *
 * `NO_ACTION_OUTCOME` is deliberately NOT a gate: it is the record that there
 * was no order to send, and showing it as a block would turn every quiet bar of
 * the day into an incident.
 */
export function barGate(bar: TosBarsBar | null | undefined): BarGate | null {
  const evidence = bar?.evidence;
  if (!evidence) return null;
  const reason = evidence.halt_reason ?? evidence.withheld_reason ?? evidence.consumed_halt_reason ?? null;
  if (!reason || reason === 'NO_ACTION_OUTCOME') return null;
  const step =
    evidence.halt_reason != null
      ? (evidence.halt_step ?? null)
      : evidence.withheld_reason != null
        ? null
        : (evidence.consumed_halt_step ?? null);
  return {
    reason,
    step,
    label: step ? `${glossaryLabel(step)} — ${glossaryLabel(reason)}` : glossaryLabel(reason),
    detail: evidence.halt_detail ?? null,
  };
}

// ---------------------------------------------------------------------------
// The verdict for one bar
// ---------------------------------------------------------------------------

export type VerdictKind = 'entry' | 'exit' | 'probe' | 'none' | 'withheld' | 'unjoined';

export interface BarVerdict {
  kind: VerdictKind;
  /** The one phrase: 진입 · 청산 · 시험 진입 · 신호 없음 · 평가 보류 · 대조 불가. */
  headline: string;
  /** The rule that decided, raw, for the secondary line. */
  ruleId: string | null;
  /** The conditions that were false — only when the verdict is 「신호 없음」. */
  failing: string[];
  /** The gate that stopped an otherwise-decided bar. */
  gate: BarGate | null;
  /** True when the strategy decided and a gate then stopped it. */
  blocked: boolean;
}

const HEADLINES: Record<VerdictKind, string> = {
  entry: '진입',
  exit: '청산',
  probe: '시험 진입',
  none: '신호 없음',
  withheld: '평가 보류',
  unjoined: '대조 불가',
};

/**
 * What happened on this bar, in the operator's terms.
 *
 * The order matters: a bar that was never evaluated cannot be reported as
 * «신호 없음», because that phrase claims the conditions were checked and came
 * out false. `evaluation` says which of the two it was.
 */
export function barVerdict(bar: TosBarsBar): BarVerdict {
  const gate = barGate(bar);
  if (bar.evaluation === 'withheld') {
    return { kind: 'withheld', headline: HEADLINES.withheld, ruleId: null, failing: [], gate, blocked: false };
  }
  if (bar.evaluation === 'journal_unjoined') {
    return { kind: 'unjoined', headline: HEADLINES.unjoined, ruleId: null, failing: [], gate, blocked: false };
  }
  const ruleId = bar.decision_rule_id ?? null;
  const kind: VerdictKind = isProbeRule(ruleId)
    ? 'probe'
    : bar.decision_kind === 'ACTION'
      ? 'entry'
      : bar.decision_kind === 'FLAT'
        ? 'exit'
        : 'none';
  if (kind === 'none') {
    const progress = entryProgress(bar);
    return {
      kind,
      headline: HEADLINES.none,
      ruleId,
      failing: progress?.failing ?? [],
      gate: null,
      blocked: false,
    };
  }
  return { kind, headline: HEADLINES[kind], ruleId, failing: [], gate, blocked: gate != null };
}

/**
 * The identity of a verdict, for collapsing a run of identical bars.
 *
 * Two bars share a key when an operator reading the timeline would learn
 * nothing from the second — same verdict, same rule, same gate, **and the same
 * failing conditions**.
 *
 * The failing set is part of the identity because the row PRINTS it. Without
 * it, a run that starts «미충족: 진입 시간대, RSI 과매도» and continues after the
 * window opens with only «RSI 과매도» collapses into the first bar's wording,
 * and the page then states the entry window was shut on bars where it was
 * open. That is a wrong claim about a real session, not a cosmetic merge.
 */
export function verdictKey(verdict: BarVerdict): string {
  return [
    verdict.kind,
    verdict.ruleId ?? '',
    verdict.gate?.reason ?? '',
    verdict.gate?.step ?? '',
    verdict.failing.join(','),
  ].join('|');
}

export interface TimelineEntry {
  /** Index into the document's `bars`, so a row can select that bar. */
  index: number;
  timeKst: string | null;
  verdict: BarVerdict;
  /** How many consecutive bars carried this same verdict, including this one. */
  run: number;
}

/**
 * Whether a row is one the operator came here for.
 *
 * Entries, exits and probes are what the session DID; «신호 없음», withheld and
 * unjoined are the quiet background between them. Only the background may ever
 * be trimmed, and even then only with its count stated — a trade that happened
 * must never be unreachable on a page whose job is to explain the day.
 */
export function isSignalVerdict(kind: VerdictKind): boolean {
  return kind === 'entry' || kind === 'exit' || kind === 'probe';
}

/**
 * The session as a list of CHANGES, not of bars.
 *
 * A 380-bar session with four distinct verdicts is four lines here. The run
 * length carries what the collapsed bars would have said, so nothing is hidden
 * — only repeated.
 */
export function verdictTimeline(bars: TosBarsBar[]): TimelineEntry[] {
  const entries: TimelineEntry[] = [];
  let lastKey: string | null = null;
  bars.forEach((bar, index) => {
    const verdict = barVerdict(bar);
    const key = verdictKey(verdict);
    if (key === lastKey && entries.length) {
      entries[entries.length - 1].run += 1;
      return;
    }
    lastKey = key;
    entries.push({ index, timeKst: bar.time_kst ?? null, verdict, run: 1 });
  });
  return entries;
}

export interface SignalCount {
  /** Bars whose decision was of this kind. */
  bars: number;
  /** Of those, the ones no kernel gate stopped. */
  passed: number;
}

export interface TimelineSummary {
  entry: SignalCount;
  exit: SignalCount;
  probe: SignalCount;
  /** How many stretches of «신호 없음» the day had. */
  quietRuns: number;
  withheldRuns: number;
  unjoinedRuns: number;
}

/**
 * What the session did, in counts, before a single row is read.
 *
 * Signals are counted in BARS (a collapsed run of three identical gated exits
 * is three), the quiet stretches in runs — which is how an operator says it:
 * «진입 신호 6번, 그중 1번만 나갔고, 그 사이 조용한 구간이 40개».
 */
export function timelineSummary(entries: TimelineEntry[]): TimelineSummary {
  const summary: TimelineSummary = {
    entry: { bars: 0, passed: 0 },
    exit: { bars: 0, passed: 0 },
    probe: { bars: 0, passed: 0 },
    quietRuns: 0,
    withheldRuns: 0,
    unjoinedRuns: 0,
  };
  for (const row of entries) {
    const { kind, gate } = row.verdict;
    if (kind === 'entry' || kind === 'exit' || kind === 'probe') {
      summary[kind].bars += row.run;
      if (!gate) summary[kind].passed += row.run;
    } else if (kind === 'none') summary.quietRuns += 1;
    else if (kind === 'withheld') summary.withheldRuns += 1;
    else summary.unjoinedRuns += 1;
  }
  return summary;
}

export interface OmittedRows {
  kind: VerdictKind;
  count: number;
}

export interface TimelinePlan {
  /** Every row the page will render, in the document's order. */
  shown: TimelineEntry[];
  /** The quiet rows left out, by kind, so the page can name them exactly. */
  omitted: OmittedRows[];
}

/**
 * Which rows to render, when there are more than a page can hold.
 *
 * **Every signal row is kept, always.** The cap applies only to the quiet
 * background, and what it drops is reported by kind rather than as a total —
 * «신호 없음 31구간을 접었습니다» is actionable, «65줄 생략» is not.
 *
 * This replaces a flat cap that dropped rows off the end of the list. On
 * `stock-005380-r1-20261125` that cap fell at row 40 and the day's actual
 * entry (11:18, ungated) was row 41: the page showed the fill in 거래 현황 and
 * refused to show the decision behind it, even under «더 보기».
 */
export function planTimeline(entries: TimelineEntry[], quietMax: number): TimelinePlan {
  const shown: TimelineEntry[] = [];
  const dropped = new Map<VerdictKind, number>();
  let quietKept = 0;
  for (const row of entries) {
    if (isSignalVerdict(row.verdict.kind)) {
      shown.push(row);
      continue;
    }
    if (quietKept < quietMax) {
      shown.push(row);
      quietKept += 1;
      continue;
    }
    dropped.set(row.verdict.kind, (dropped.get(row.verdict.kind) ?? 0) + 1);
  }
  return {
    shown,
    omitted: [...dropped.entries()].map(([kind, count]) => ({ kind, count })),
  };
}

// ---------------------------------------------------------------------------
// The day in aggregate
// ---------------------------------------------------------------------------

export interface BlockingCondition {
  name: string;
  termKey: string | null;
  expression: string;
  failedBars: number | null;
  bars: number | null;
  failedPct: number | null;
}

/**
 * Which entry condition was false on the largest share of judged bars.
 *
 * The summary's own denominator is the counted bars, so this answers «오늘
 * 진입을 막은 조건» over the bars the engine actually judged — withheld and
 * journal-substituted bars are already excluded upstream and must not be
 * reintroduced here.
 */
export function entryBlockers(summary: TosBarsSummary | null | undefined): BlockingCondition[] {
  const rules = summary?.rules ?? [];
  const entry = rules.find((rule) => !isProbeRule(rule.rule_id) && /ENTRY/.test(rule.rule_id ?? ''));
  if (!entry) return [];
  return (entry.compares ?? [])
    .map((compare) => {
      const parsed = parseCompare(compare.expression);
      const leftName = parsed?.left ?? '';
      return {
        name: leftName ? glossaryLabel(leftName) : (compare.expression ?? '알 수 없음'),
        termKey: leftName ? glossaryKey(leftName) : null,
        expression: compare.expression ?? '',
        failedBars: compare.failed_bars ?? null,
        bars: compare.bars ?? null,
        failedPct: compare.failed_pct ?? null,
      };
    })
    .sort((a, b) => (b.failedPct ?? -1) - (a.failedPct ?? -1));
}

/** The summary row for the entry rule, for «오늘 진입 신호 n회». */
export function entrySummaryRule(summary: TosBarsSummary | null | undefined): TosBarsSummaryRule | null {
  const rules = summary?.rules ?? [];
  return rules.find((rule) => !isProbeRule(rule.rule_id) && /ENTRY/.test(rule.rule_id ?? '')) ?? null;
}

export interface ProbeTally {
  /** Bars whose decision was the probe rule. */
  fired: number;
  /** Of those, the ones no kernel gate stopped — the orders that were sent. */
  passed: number;
  /** Where the rest stopped, commonest first. */
  gates: { code: string; label: string; count: number }[];
}

/**
 * How often the order-path probe fired, and how often an order actually left.
 *
 * The two numbers are far apart and the difference is the point: on
 * 2026-11-25 the 005930 tree fired 325 probe decisions and sent one order.
 * Printing only 「325회」 invites the reading that the day placed 325 trades,
 * which is wrong by two orders of magnitude.
 */
export function probeTally(bars: TosBarsBar[] | null | undefined): ProbeTally {
  const counts = new Map<string, { label: string; count: number }>();
  let fired = 0;
  let passed = 0;
  for (const bar of bars ?? []) {
    if (!isProbeRule(bar.decision_rule_id)) continue;
    fired += 1;
    const gate = barGate(bar);
    if (!gate) {
      passed += 1;
      continue;
    }
    const code = gate.step ? `${gate.reason}@${gate.step}` : gate.reason;
    const entry = counts.get(code);
    if (entry) entry.count += 1;
    else counts.set(code, { label: gate.label, count: 1 });
  }
  const gates = [...counts.entries()]
    .map(([code, value]) => ({ code, label: value.label, count: value.count }))
    .sort((a, b) => b.count - a.count);
  return { fired, passed, gates };
}

/** The last bar the engine actually judged — what «지금» means for a tenant. */
export function latestCountedBar(bars: TosBarsBar[] | null | undefined): TosBarsBar | null {
  const list = bars ?? [];
  for (let index = list.length - 1; index >= 0; index -= 1) {
    if (list[index].counted === true) return list[index];
  }
  return null;
}

/** How many bars of the session a gate stopped, across every gate. */
export function gateTally(summary: TosBarsSummary | null | undefined): { label: string; code: string; count: number }[] {
  const halts = summary?.evidence_halts ?? null;
  if (!halts) return [];
  return Object.entries(halts)
    .map(([code, count]) => {
      const [reason, step] = code.split('@');
      return {
        code,
        label: step ? `${glossaryLabel(step)} — ${glossaryLabel(reason)}` : glossaryLabel(reason),
        count,
      };
    })
    .sort((a, b) => b.count - a.count);
}
