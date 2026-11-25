import type {
  TosBarsBar,
  TosBarsDocument,
  TosBarsExplain,
  TosBarsHypotheticalPnl,
  TosBarsRule,
} from '@/lib/dashboard/tosBars';
import type { TosStatusDocument } from '@/lib/dashboard/tosStatus';
import type { TosSymbolsDocument } from '@/lib/dashboard/tosSymbols';

// Six- and four-bar excerpts with the SHAPES the real exports carry.
//
// Every code, threshold, halt sentence and scale factor below was read out of
// `bars/long-20261125.json` and `bars/stock-r1-20261125.json` on the host —
// including the two `halt_detail` sentences verbatim, because the page renders
// them and a paraphrase here would let a wording change land untested. The
// prices, z scores and ATRs are the real ones for those bars.
//
// What is NOT copied: the documents' `data_dir`, `strategy.path` and
// `bindings.path`. The route already drops them before the body is built
// (services/dashboard/routes/tos_bars.py), they are host deployment details,
// and a fixture is a file in the repository.
//
// The summaries are computed for THESE bars rather than copied from the real
// 410-bar session, so a test that asserts a denominator is asserting something
// the fixture can be checked against by hand.

/** The stage-denial sentence the evidence writes for a close with no position. */
export const ZERO_POSITION_DETAIL =
  "quantity_basis 'ZERO_POSITION' closes a position but no held position was observed — an unknown held position is a no-send, never an assumed size (design #35 §5.2)";

/** The sentence the evidence writes when no approval decision came back. */
export const NO_APPROVAL_DETAIL =
  'no independent approval decision is available for this proposal — UNKNOWN is restrictive, never an assumed grant';

/** The sentence the evidence writes when the venue refused the order. */
export const INADMISSIBLE_DETAIL = 'venue admissibility is INADMISSIBLE';

export type Env = Record<string, boolean | number | string>;

function bool(value: boolean): string {
  return value ? 'true' : 'false';
}

/** The Setup D entry rule as the DSL emits it, evaluated against `env`. */
function setupDEntry(env: Env, zEntryMax: number): TosBarsRule {
  const compares = [
    { index: 1, expression: 'entry_window EQ true', left: bool(env.entry_window as boolean), right: 'true' },
    { index: 2, expression: 'hi_vol EQ true', left: bool(env.hi_vol as boolean), right: 'true' },
    { index: 3, expression: 'stall_ok EQ true', left: bool(env.stall_ok as boolean), right: 'true' },
    { index: 4, expression: 'reversal_ok EQ true', left: bool(env.reversal_ok as boolean), right: 'true' },
    {
      index: 5,
      expression: 'z_x1000 LE config.z_entry_max_x1000',
      left: String(env.z_x1000),
      right: String(zEntryMax),
    },
  ].map((compare) => ({
    index: compare.index,
    expression: compare.expression,
    left_value: compare.left,
    right_value: compare.right,
    passed:
      compare.index === 5 ? Number(compare.left) <= Number(compare.right) : compare.left === compare.right,
  }));
  return {
    label: 'R1',
    rule_id: 'R1-ENTRY-LONG',
    decision_kind: 'ACTION',
    fired: compares.every((compare) => compare.passed),
    compares,
  };
}

function booleanRule(
  label: string,
  ruleId: string,
  decisionKind: string,
  field: string,
  env: Env,
): TosBarsRule {
  const passed = env[field] === true;
  return {
    label,
    rule_id: ruleId,
    decision_kind: decisionKind,
    fired: passed,
    compares: [
      {
        index: 1,
        expression: `${field} EQ true`,
        left_value: bool(passed),
        right_value: 'true',
        passed,
      },
    ],
  };
}

/** The M2 order-path probe, which the strategy YAML states is not a signal. */
function probeRule(env: Env, enabled: boolean): TosBarsRule {
  const open = env.entry_window === true;
  const compares = [
    {
      index: 1,
      expression: 'entry_window EQ true',
      left_value: bool(open),
      right_value: 'true',
      passed: open,
    },
    {
      index: 2,
      expression: 'entry_window EQ config.m2_probe_entry_enabled',
      left_value: bool(open),
      right_value: bool(enabled),
      passed: open === enabled,
    },
  ];
  return {
    label: 'R4',
    rule_id: 'R4-M2-PROBE-ENTRY-LONG',
    decision_kind: 'ACTION',
    fired: compares.every((compare) => compare.passed),
    compares,
  };
}

interface BarSpec {
  time: string;
  env?: Env;
  /** Journal values for a bar the engine did not evaluate. */
  fields?: Env;
  evaluation: 'engine_view' | 'withheld' | 'journal_unjoined';
  decisionKind?: string | null;
  decisionRuleId?: string | null;
  halt?: { reason: string; step: string | null; detail: string | null };
  withheldReason?: string;
  unjoinedReason?: string;
  outcomeType?: string | null;
  flags?: string;
  probe?: boolean;
}

function makeBar(spec: BarSpec, zEntryMax: number): TosBarsBar {
  const env = spec.env ?? {};
  const counted = spec.evaluation === 'engine_view';
  const rules: TosBarsRule[] = counted
    ? [
        setupDEntry(env, zEntryMax),
        booleanRule('R2', 'R2-EXIT-VWAP-REVERTED', 'FLAT', 'vwap_reverted', env),
        booleanRule('R3', 'R3-EXIT-EOD', 'FLAT', 'eod', env),
        ...(spec.probe ? [probeRule(env, true)] : []),
      ]
    : [];
  return {
    raw_event_id: `A05612:1m:${spec.time.replace(':', '')}`,
    as_of_ms: null,
    time_kst: spec.time,
    time_source: 'raw_event_id',
    fields: spec.fields ?? env,
    env_values: counted ? env : {},
    evaluation: spec.evaluation,
    counted,
    flags: spec.flags ?? '----',
    view_diff: {},
    engine_shape: counted ? (spec.decisionKind === 'NO_ACTION' ? 'no_action' : 'proposal') : null,
    decision_disagrees: false,
    decision_rule_id: spec.decisionRuleId ?? null,
    decision_kind: spec.decisionKind ?? null,
    rules,
    evidence: {
      joined: spec.evaluation !== 'journal_unjoined',
      unjoined_reason: spec.unjoinedReason ?? null,
      event_id: `event-${spec.time}`,
      snapshot_id: `cis-${spec.time}`,
      outcome_type: spec.outcomeType ?? null,
      outcome_halt_reason: spec.decisionKind === 'NO_ACTION' ? 'NO_ACTION_OUTCOME' : null,
      consumed_halt_reason:
        spec.halt?.reason ?? spec.withheldReason ?? (spec.decisionKind === 'NO_ACTION' ? 'NO_ACTION_OUTCOME' : null),
      consumed_halt_step: spec.halt?.step ?? null,
      withheld_reason: spec.withheldReason ?? null,
      halt_step: spec.halt?.step ?? null,
      halt_reason: spec.halt?.reason ?? null,
      halt_detail: spec.halt?.detail ?? null,
      value_view: counted ? env : {},
      value_view_refusal: null,
    },
  };
}

const QUIET: Env = {
  atr14_x100: 331,
  close_x100: 74414,
  entry_window: false,
  eod: false,
  hi_vol: false,
  high_x100: 74638,
  low_x100: 74372,
  open_x100: 74638,
  reversal_ok: false,
  session_token: '2026-11-25',
  stall_ok: false,
  volume: 478,
  vwap_reverted: false,
  vwap_x100: 74563,
  z_x1000: -451,
};

const REVERTED: Env = { ...QUIET, close_x100: 74524, vwap_x100: 74528, z_x1000: -12, vwap_reverted: true };

/** The real 09:14 bar: every Setup D gate open and z past the entry threshold. */
const ENTRY: Env = {
  atr14_x100: 228,
  close_x100: 73564,
  entry_window: true,
  eod: false,
  hi_vol: true,
  high_x100: 73572,
  low_x100: 73400,
  open_x100: 73428,
  reversal_ok: true,
  session_token: '2026-11-25',
  stall_ok: true,
  volume: 853,
  vwap_reverted: false,
  vwap_x100: 74106,
  z_x1000: -2377,
};

const EOD: Env = {
  ...QUIET,
  close_x100: 74200,
  vwap_x100: 74250,
  z_x1000: -200,
  eod: true,
  hi_vol: true,
};

/**
 * A futures session: quiet, one gated exit, one gated entry, one EOD close,
 * plus the two bars the engine did not judge.
 *
 * Decision-only, which is why every proposal on it ends at a gate: a tree with
 * no position cannot close one, and no approval comes back for an open.
 */

// ---------------------------------------------------------------------------
// The P2 blocks: what the rules MEAN, and what the decisions would have earned
// ---------------------------------------------------------------------------
//
// `rationale`, `probe` and the field definitions below are copied verbatim out
// of the same two exports the bars above came from. Verbatim matters twice
// over: the page prints the sentence unchanged, and `probe: true` is the
// operator map's assertion (`config/tos_bars_explain.yaml`,
// `probe_basis: OPERATOR_RULE_MAP`) rather than a word read out of the rule id
// — a fixture that paraphrased either would let the real wording drift
// untested.

/** The field catalog entries the Setup D rules stand on. */
const SETUP_D_FIELDS: NonNullable<TosBarsExplain['fields']> = {
  entry_window: {
    field: 'entry_window',
    op: 'between',
    inputs: ['mso'],
    params: { hi: 345, lo: 15 },
    published_as: 'entry_window',
    known: true,
  },
  hi_vol: {
    field: 'hi_vol',
    op: 'all',
    inputs: ['usable', 'vol_pass'],
    params: null,
    published_as: 'hi_vol',
    known: true,
  },
  stall_ok: {
    field: 'stall_ok',
    op: 'all',
    inputs: ['through_extreme', 'stall_short_gate', 'stall_long_gate'],
    params: null,
    published_as: 'stall_ok',
    known: true,
  },
  reversal_ok: {
    field: 'reversal_ok',
    op: 'all',
    inputs: ['stall_ok', 'prev_close_known', 'turn_long_gate', 'turn_short_gate', 'improve_ok'],
    params: null,
    published_as: 'reversal_ok',
    known: true,
  },
  z_x1000: {
    field: 'z',
    op: 'ratio_z',
    inputs: ['close', 'vwap', 'atr'],
    params: null,
    published_as: 'z_x1000',
    scale: { mult: 1000, round: 'toward_zero' },
    known: true,
  },
  vwap_reverted: {
    field: 'vwap_reverted',
    op: 'le',
    inputs: ['abs_z'],
    params: { const: 0.2 },
    published_as: 'vwap_reverted',
    known: true,
  },
  eod: {
    field: 'eod',
    op: 'time_ge',
    inputs: [],
    params: { at: '15:15' },
    published_as: 'eod',
    known: true,
  },
};

const NO_ACTION_DEFAULT = {
  rule_id: 'R0-DEFAULT-NO-ACTION',
  decision_kind: 'NO_ACTION',
  rationale: 'R0-DEFAULT-NO-ACTION: no rule fired — hold exposure unchanged.',
};

/** The explain block of a Setup D tree, with the probe rule only where it runs. */
export function setupDExplain({ probe = false }: { probe?: boolean } = {}): TosBarsExplain {
  const rules: NonNullable<TosBarsExplain['rules']> = [
    {
      label: 'R1',
      rule_id: 'R1-ENTRY-LONG',
      decision_kind: 'ACTION',
      probe: false,
      rationale:
        'R1-ENTRY-LONG: entry window open, high-volatility regime, stall guard clear, reversal confirmed, and the VWAP extension has reached the LONG extreme threshold — propose a new long.',
      target_rationale:
        'R1-ENTRY-LONG: open a new long at the LONG-side VWAP extreme with every Setup D gate satisfied.',
      fields: ['entry_window', 'hi_vol', 'stall_ok', 'reversal_ok', 'z_x1000'],
      bindings: ['z_entry_max_x1000'],
    },
    {
      label: 'R2',
      rule_id: 'R2-EXIT-VWAP-REVERTED',
      decision_kind: 'FLAT',
      probe: false,
      rationale:
        'R2-EXIT-VWAP-REVERTED: price has returned to the VWAP band — the mean-reversion thesis is realized, go flat.',
      fields: ['vwap_reverted'],
      bindings: [],
    },
    {
      label: 'R3',
      rule_id: 'R3-EXIT-EOD',
      decision_kind: 'FLAT',
      probe: false,
      rationale: "R3-EXIT-EOD: the session's EOD close time has arrived — go flat.",
      fields: ['eod'],
      bindings: [],
    },
  ];
  if (probe) {
    rules.push({
      label: 'R4',
      rule_id: 'R4-M2-PROBE-ENTRY-LONG',
      decision_kind: 'ACTION',
      probe: true,
      rationale:
        "R4-M2-PROBE-ENTRY-LONG: M2 boundary probe, NOT a Setup D signal — the entry window is open and the operator's M2 probe binding is on, so propose one long to exercise the approval/reservation/verify/ kis_mock send/result/finality boundary end to end.",
      fields: ['entry_window'],
      bindings: ['m2_probe_entry_enabled'],
    });
  }
  return {
    schema: 'tos-bars-explain/1',
    rules,
    default: NO_ACTION_DEFAULT,
    fields: SETUP_D_FIELDS,
    probe_basis: 'OPERATOR_RULE_MAP',
  };
}

/** The RSI/%R tenant's own rule set — a different vocabulary on purpose. */
export function rsiExplain(): TosBarsExplain {
  const permissive = (field: string) => ({
    field,
    op: 'permissive',
    inputs: [`${field}_raw`],
    params: { when_missing: false },
    published_as: field,
    known: true,
  });
  return {
    schema: 'tos-bars-explain/1',
    rules: [
      {
        label: 'R1',
        rule_id: 'R1-ENTRY-LONG-RSI-WR',
        decision_kind: 'ACTION',
        probe: false,
        rationale:
          'R1-ENTRY-LONG-RSI-WR: entry window open, RSI(14) at or below its oversold line and Williams %R(14) at or below its own — both momentum readings say the pullback is stretched, so propose a new long.',
        fields: ['entry_window', 'rsi_oversold', 'wr_oversold'],
        bindings: [],
      },
      {
        label: 'R2',
        rule_id: 'R2-EXIT-RSI-RECOVERED',
        decision_kind: 'FLAT',
        probe: false,
        rationale:
          'R2-EXIT-RSI-RECOVERED: RSI(14) has climbed back to its midline — the mean-reversion thesis is realized, go flat.',
        fields: ['rsi_recovered'],
        bindings: [],
      },
      {
        label: 'R3',
        rule_id: 'R3-EXIT-EOD',
        decision_kind: 'FLAT',
        probe: false,
        rationale: "R3-EXIT-EOD: the session's EOD close time has arrived — go flat.",
        fields: ['eod'],
        bindings: [],
      },
    ],
    default: NO_ACTION_DEFAULT,
    fields: {
      entry_window: SETUP_D_FIELDS.entry_window,
      eod: SETUP_D_FIELDS.eod,
      rsi_oversold: permissive('rsi_oversold'),
      wr_oversold: permissive('wr_oversold'),
      rsi_recovered: permissive('rsi_recovered'),
    },
  };
}

/**
 * The futures tree's hypothetical PnL — one would-have-been round trip.
 *
 * Both leg times name bars this fixture actually carries, so the chart marks
 * land on real indices, and the skipped decision is the shape the real export
 * produced on 2026-11-25: a close the inspection re-derived rather than one
 * the engine made, left out of the total with its reason stated.
 */
export function futuresHypothetical(): TosBarsHypotheticalPnl {
  return {
    hypothetical: true,
    direction: 'LONG',
    instrument: 'A05612',
    contract: 'kospi200_mini',
    multiplier_krw_per_point: 50000,
    price_field: 'close_x100',
    price_scale: 100,
    assumptions: [
      'FILL_AT_DECISION_BAR_CLOSE',
      'FILL_ALWAYS_ASSUMED',
      'NO_FEES',
      'NO_SLIPPAGE',
      'ONE_CONTRACT',
      'ONE_POSITION_AT_A_TIME',
    ],
    trades: [
      {
        entry_time_kst: '09:14',
        entry_rule_id: 'R1-ENTRY-LONG',
        entry_price_points: '735.64',
        exit_time_kst: '15:45',
        exit_rule_id: 'R3-EXIT-EOD',
        exit_price_points: '738.58',
        points: '2.94',
        hypothetical_pnl_krw: '147000',
        forced_close: false,
        forced_close_reason: null,
      },
    ],
    totals: {
      trades: 1,
      wins: 1,
      points: '2.94',
      hypothetical_pnl_krw: '147000',
      forced_closes: 0,
    },
    unpriced_decisions: [],
    skipped_decisions: [
      {
        time_kst: '08:48',
        decision_kind: 'FLAT',
        rule_id: 'R2-EXIT-VWAP-REVERTED',
        reason: 'NOT_ENGINE_COUNTED',
      },
    ],
  };
}

export function futuresBarsDocument(): TosBarsDocument {
  const z = -1800;
  const bars = [
    makeBar(
      {
        time: '08:45',
        evaluation: 'withheld',
        fields: { close_x100: 74420, vwap_x100: 74500 },
        withheldReason: 'TIME_NOT_ADMITTED',
        flags: '--W-',
      },
      z,
    ),
    makeBar(
      {
        time: '08:46',
        env: QUIET,
        evaluation: 'engine_view',
        decisionKind: 'NO_ACTION',
        decisionRuleId: 'R0-DEFAULT-NO-ACTION',
        outcomeType: 'NoActionOutcome',
      },
      z,
    ),
    makeBar(
      {
        time: '08:48',
        env: REVERTED,
        evaluation: 'engine_view',
        decisionKind: 'FLAT',
        decisionRuleId: 'R2-EXIT-VWAP-REVERTED',
        outcomeType: 'Proposal',
        halt: {
          reason: 'STAGE_DENIED',
          step: 'CANDIDATE_COMMAND_CONSTRUCTION',
          detail: ZERO_POSITION_DETAIL,
        },
      },
      z,
    ),
    makeBar(
      {
        time: '09:00',
        evaluation: 'journal_unjoined',
        fields: { close_x100: 74000, vwap_x100: 74300 },
        unjoinedReason: 'no preimage row names this raw_event_id',
        flags: '---U',
      },
      z,
    ),
    makeBar(
      {
        time: '09:14',
        env: ENTRY,
        evaluation: 'engine_view',
        decisionKind: 'ACTION',
        decisionRuleId: 'R1-ENTRY-LONG',
        outcomeType: 'Proposal',
        halt: { reason: 'STAGE_UNKNOWN', step: 'INDEPENDENT_APPROVAL', detail: NO_APPROVAL_DETAIL },
      },
      z,
    ),
    makeBar(
      {
        time: '15:45',
        env: EOD,
        evaluation: 'engine_view',
        decisionKind: 'FLAT',
        decisionRuleId: 'R3-EXIT-EOD',
        outcomeType: 'Proposal',
        halt: {
          reason: 'STAGE_DENIED',
          step: 'CANDIDATE_COMMAND_CONSTRUCTION',
          detail: ZERO_POSITION_DETAIL,
        },
      },
      z,
    ),
  ];

  return {
    schema_version: 1,
    session: 'long-20261125',
    instrument: 'A05612',
    market: 'futures',
    decision_only: true,
    final: true,
    explain: setupDExplain(),
    hypothetical_pnl: futuresHypothetical(),
    strategy: { sha256: 'aa6b6fee3b7c08de1e95c9c45593c8c49d6898c5fd862568f6e3a226e8222eee' },
    bindings: { values: { z_entry_max_x1000: z } },
    window: { from: null, to: null },
    default: { rule_id: 'R0-DEFAULT-NO-ACTION', decision_kind: 'NO_ACTION' },
    bars,
    summary: {
      bars: 6,
      counted_bars: 4,
      withheld_bars: 1,
      substituted_bars: 1,
      view_diff_bars: 0,
      view_diff_fields: {},
      disagreement_bars: 0,
      not_comparable_bars: 0,
      rules: [
        {
          label: 'R1',
          rule_id: 'R1-ENTRY-LONG',
          fired_bars: 1,
          bars: 4,
          fired_pct: 25,
          compares: [
            { index: 1, expression: 'entry_window EQ true', failed_bars: 3, bars: 4, failed_pct: 75 },
            { index: 2, expression: 'hi_vol EQ true', failed_bars: 2, bars: 4, failed_pct: 50 },
            { index: 3, expression: 'stall_ok EQ true', failed_bars: 3, bars: 4, failed_pct: 75 },
            { index: 4, expression: 'reversal_ok EQ true', failed_bars: 3, bars: 4, failed_pct: 75 },
            {
              index: 5,
              expression: 'z_x1000 LE config.z_entry_max_x1000',
              failed_bars: 3,
              bars: 4,
              failed_pct: 75,
            },
          ],
        },
        {
          label: 'R2',
          rule_id: 'R2-EXIT-VWAP-REVERTED',
          fired_bars: 1,
          bars: 4,
          fired_pct: 25,
          compares: [
            { index: 1, expression: 'vwap_reverted EQ true', failed_bars: 3, bars: 4, failed_pct: 75 },
          ],
        },
        {
          label: 'R3',
          rule_id: 'R3-EXIT-EOD',
          fired_bars: 1,
          bars: 4,
          fired_pct: 25,
          compares: [{ index: 1, expression: 'eod EQ true', failed_bars: 3, bars: 4, failed_pct: 75 }],
        },
      ],
      decisions: {
        'R0-DEFAULT-NO-ACTION': 1,
        'R1-ENTRY-LONG': 1,
        'R2-EXIT-VWAP-REVERTED': 1,
        'R3-EXIT-EOD': 1,
      },
      evidence_outcomes: { NoActionOutcome: 1, Proposal: 3, TIME_NOT_ADMITTED: 1 },
      evidence_halts: {
        'STAGE_DENIED@CANDIDATE_COMMAND_CONSTRUCTION': 2,
        'STAGE_UNKNOWN@INDEPENDENT_APPROVAL': 1,
      },
      unjoined: { 'no preimage row names this raw_event_id': 1 },
      value_view_refused: {},
    },
  };
}

/** The real 09:15 probe bar on 005930 — the one that produced a mock fill. */
const PROBE_ENV: Env = {
  atr14_x100: 63571,
  close_x100: 17560000,
  entry_window: true,
  eod: false,
  hi_vol: true,
  high_x100: 17600000,
  low_x100: 17550000,
  open_x100: 17590000,
  reversal_ok: false,
  session_token: '2026-11-25',
  stall_ok: false,
  volume: 86461,
  vwap_reverted: false,
  vwap_x100: 17780262,
  z_x1000: -3464,
};

/**
 * A stock session: the M2 probe fires, once cleanly and once into a gate, and
 * the EOD close is refused by the venue.
 *
 * This is the tenant with an order path, so the three gate codes an operator
 * actually sees on a trading day are all present on one document.
 */
export function stockBarsDocument(): TosBarsDocument {
  const z = -1800;
  const bars = [
    makeBar(
      {
        time: '09:00',
        evaluation: 'withheld',
        fields: { close_x100: 17600000, vwap_x100: 17600000 },
        withheldReason: 'TIME_NOT_ADMITTED',
        flags: '--W-',
        probe: true,
      },
      z,
    ),
    makeBar(
      {
        time: '09:15',
        env: PROBE_ENV,
        evaluation: 'engine_view',
        decisionKind: 'ACTION',
        decisionRuleId: 'R4-M2-PROBE-ENTRY-LONG',
        outcomeType: 'Proposal',
        probe: true,
      },
      z,
    ),
    makeBar(
      {
        time: '09:20',
        env: { ...PROBE_ENV, close_x100: 17540000, z_x1000: -3600 },
        evaluation: 'engine_view',
        decisionKind: 'ACTION',
        decisionRuleId: 'R4-M2-PROBE-ENTRY-LONG',
        outcomeType: 'Proposal',
        halt: { reason: 'STAGE_UNKNOWN', step: 'INDEPENDENT_APPROVAL', detail: NO_APPROVAL_DETAIL },
        probe: true,
      },
      z,
    ),
    makeBar(
      {
        time: '15:15',
        env: { ...PROBE_ENV, entry_window: false, eod: true, hi_vol: false },
        evaluation: 'engine_view',
        decisionKind: 'FLAT',
        decisionRuleId: 'R3-EXIT-EOD',
        outcomeType: 'Proposal',
        halt: {
          reason: 'STAGE_DENIED',
          step: 'VENUE_ADMISSIBILITY_DECISION',
          detail: INADMISSIBLE_DETAIL,
        },
        probe: true,
      },
      z,
    ),
  ];

  return {
    schema_version: 1,
    session: 'stock-r1-20261125',
    instrument: '005930',
    market: 'stock',
    decision_only: false,
    final: true,
    explain: setupDExplain({ probe: true }),
    strategy: { sha256: 'df164ee2461aa133ac6506889cd53c3618134a42403e2c302128cb3c54fd3b00' },
    bindings: { values: { m2_probe_entry_enabled: true, z_entry_max_x1000: z } },
    window: { from: null, to: null },
    default: { rule_id: 'R0-DEFAULT-NO-ACTION', decision_kind: 'NO_ACTION' },
    bars,
    summary: {
      bars: 4,
      counted_bars: 3,
      withheld_bars: 1,
      substituted_bars: 0,
      view_diff_bars: 0,
      view_diff_fields: {},
      disagreement_bars: 0,
      not_comparable_bars: 0,
      rules: [
        {
          label: 'R1',
          rule_id: 'R1-ENTRY-LONG',
          fired_bars: 0,
          bars: 3,
          fired_pct: 0,
          compares: [
            { index: 1, expression: 'entry_window EQ true', failed_bars: 1, bars: 3, failed_pct: 33.3333 },
            { index: 2, expression: 'hi_vol EQ true', failed_bars: 1, bars: 3, failed_pct: 33.3333 },
            { index: 3, expression: 'stall_ok EQ true', failed_bars: 3, bars: 3, failed_pct: 100 },
            { index: 4, expression: 'reversal_ok EQ true', failed_bars: 3, bars: 3, failed_pct: 100 },
            {
              index: 5,
              expression: 'z_x1000 LE config.z_entry_max_x1000',
              failed_bars: 0,
              bars: 3,
              failed_pct: 0,
            },
          ],
        },
        {
          label: 'R4',
          rule_id: 'R4-M2-PROBE-ENTRY-LONG',
          fired_bars: 2,
          bars: 3,
          fired_pct: 66.6667,
          compares: [
            { index: 1, expression: 'entry_window EQ true', failed_bars: 1, bars: 3, failed_pct: 33.3333 },
            {
              index: 2,
              expression: 'entry_window EQ config.m2_probe_entry_enabled',
              failed_bars: 1,
              bars: 3,
              failed_pct: 33.3333,
            },
          ],
        },
      ],
      decisions: { 'R3-EXIT-EOD': 1, 'R4-M2-PROBE-ENTRY-LONG': 2 },
      evidence_outcomes: { Proposal: 3, TIME_NOT_ADMITTED: 1 },
      evidence_halts: {
        'STAGE_UNKNOWN@INDEPENDENT_APPROVAL': 1,
        'STAGE_DENIED@VENUE_ADMISSIBILITY_DECISION': 1,
      },
      unjoined: {},
      value_view_refused: {},
    },
  };
}

/**
 * A quiet NO_ACTION bar, with `env` overriding the baseline.
 *
 * For the case the timeline gets wrong if its run key forgets the failing
 * set: two adjacent bars that are both «신호 없음» but fail different
 * conditions, because the entry window opened between them.
 */
export function quietBar(time: string, env: Env = {}): TosBarsBar {
  return makeBar(
    {
      time,
      env: { ...QUIET, ...env },
      evaluation: 'engine_view',
      decisionKind: 'NO_ACTION',
      decisionRuleId: 'R0-DEFAULT-NO-ACTION',
      outcomeType: 'NoActionOutcome',
    },
    -1800,
  );
}

/**
 * A long quiet morning, then the day's one real trade — the 005380 shape.
 *
 * `quietChanges` distinct «신호 없음» rows (the failing set alternates, so each
 * is its own row) followed by an UNGATED entry and an ungated exit. With a flat
 * cap of forty rows the two that matter fell off the end: 거래 현황 showed the
 * fill while the timeline refused to show the decision behind it. Any future
 * trimming has to keep them reachable.
 */
export function quietThenTradeDocument(quietChanges = 42): TosBarsDocument {
  const bars: TosBarsBar[] = [];
  for (let index = 0; index < quietChanges; index += 1) {
    const minute = (index % 60).toString().padStart(2, '0');
    const hour = (9 + Math.floor(index / 60)).toString().padStart(2, '0');
    // Alternating the volatility gate makes every bar a change of its own.
    bars.push(quietBar(`${hour}:${minute}`, { entry_window: true, hi_vol: index % 2 === 0 }));
  }
  bars.push(
    makeBar(
      {
        time: '11:18',
        env: ENTRY,
        evaluation: 'engine_view',
        decisionKind: 'ACTION',
        decisionRuleId: 'R1-ENTRY-LONG',
        outcomeType: 'Proposal',
      },
      -1800,
    ),
    makeBar(
      {
        time: '11:26',
        env: { ...REVERTED, entry_window: true },
        evaluation: 'engine_view',
        decisionKind: 'FLAT',
        decisionRuleId: 'R2-EXIT-VWAP-REVERTED',
        outcomeType: 'Proposal',
      },
      -1800,
    ),
  );
  return { ...futuresBarsDocument(), session: 'quiet-then-trade-20261125', bars };
}

/** The RSI/%R entry rule 005380 runs instead of Setup D's. */
function rsiEntry(env: Env): TosBarsRule {
  const compares = [
    { index: 1, field: 'entry_window' },
    { index: 2, field: 'rsi_oversold' },
    { index: 3, field: 'wr_oversold' },
  ].map(({ index, field }) => ({
    index,
    expression: `${field} EQ true`,
    left_value: bool(env[field] === true),
    right_value: 'true',
    passed: env[field] === true,
  }));
  return {
    label: 'R1',
    rule_id: 'R1-ENTRY-LONG-RSI-WR',
    decision_kind: 'ACTION',
    fired: compares.every((compare) => compare.passed),
    compares,
  };
}

/**
 * The 005380 tenant, whose rule set is NOT Setup D's.
 *
 * It exists in the suite because every "the entry rule is R1-ENTRY-LONG"
 * shortcut this page could take would pass on the other four tenants and be
 * wrong here. The published fields are its own
 * (`config/tos_runtime/cp3-setup-d-stock-005380/fields.yaml`): no z, no
 * hi_vol, no stall_ok.
 */
export function rsiStockBarsDocument(): TosBarsDocument {
  const base: Env = {
    atr14_x100: 21000,
    close_x100: 26650000,
    entry_window: false,
    eod: false,
    high_x100: 26700000,
    low_x100: 26600000,
    open_x100: 26650000,
    rsi_oversold: false,
    rsi_recovered: false,
    session_token: '2026-11-25',
    volume: 1200,
    vwap_x100: 26700000,
    wr_oversold: false,
  };
  const bar = (time: string, env: Env, kind: string | null, ruleId: string | null): TosBarsBar => {
    const values = { ...base, ...env };
    const built = makeBar(
      {
        time,
        env: values,
        evaluation: 'engine_view',
        decisionKind: kind,
        decisionRuleId: ruleId,
        outcomeType: kind === 'NO_ACTION' ? 'NoActionOutcome' : 'Proposal',
      },
      -1800,
    );
    return {
      ...built,
      rules: [
        rsiEntry(values),
        booleanRule('R2', 'R2-EXIT-RSI-RECOVERED', 'FLAT', 'rsi_recovered', values),
        booleanRule('R3', 'R3-EXIT-EOD', 'FLAT', 'eod', values),
      ],
    };
  };

  const bars = [
    // 09:03 — window shut AND both oversold gates false.
    bar('09:03', {}, 'NO_ACTION', 'R0-DEFAULT-NO-ACTION'),
    // 09:15 — the window has opened; only the two indicators still fail.
    bar('09:15', { entry_window: true }, 'NO_ACTION', 'R0-DEFAULT-NO-ACTION'),
    bar('09:21', { entry_window: true, rsi_oversold: true, wr_oversold: true }, 'ACTION', 'R1-ENTRY-LONG-RSI-WR'),
  ];

  return {
    schema_version: 1,
    session: 'stock-005380-r1-20261125',
    instrument: '005380',
    market: 'stock',
    decision_only: false,
    final: true,
    explain: rsiExplain(),
    strategy: { sha256: '0f0e8b6d6c3a4e5f8a9b0c1d2e3f405162738495a6b7c8d9e0f1a2b3c4d5e6f7' },
    bindings: { values: {} },
    window: { from: null, to: null },
    default: { rule_id: 'R0-DEFAULT-NO-ACTION', decision_kind: 'NO_ACTION' },
    bars,
    summary: {
      bars: 3,
      counted_bars: 3,
      withheld_bars: 0,
      substituted_bars: 0,
      view_diff_bars: 0,
      view_diff_fields: {},
      disagreement_bars: 0,
      not_comparable_bars: 0,
      rules: [
        {
          label: 'R1',
          rule_id: 'R1-ENTRY-LONG-RSI-WR',
          fired_bars: 1,
          bars: 3,
          fired_pct: 33.3333,
          compares: [
            { index: 1, expression: 'entry_window EQ true', failed_bars: 1, bars: 3, failed_pct: 33.3333 },
            { index: 2, expression: 'rsi_oversold EQ true', failed_bars: 2, bars: 3, failed_pct: 66.6667 },
            { index: 3, expression: 'wr_oversold EQ true', failed_bars: 2, bars: 3, failed_pct: 66.6667 },
          ],
        },
      ],
      decisions: { 'R0-DEFAULT-NO-ACTION': 2, 'R1-ENTRY-LONG-RSI-WR': 1 },
      evidence_outcomes: { NoActionOutcome: 2, Proposal: 1 },
      evidence_halts: {},
      unjoined: {},
      value_view_refused: {},
    },
  };
}

/**
 * Today's per-symbol rows, as `symbols/today.json` carries them.
 *
 * The broker execution ids are the mock account's own; they identify an order
 * inside KIS's paper environment and name no account.
 */
export function symbolsDocument(): TosSymbolsDocument {
  return {
    schema_version: 1,
    date: '2026-11-25',
    generated_kst: '2026-11-25T15:55:02+09:00',
    holding_basis: 'TOS_LEDGER_FIFO_OPEN_LOTS',
    symbols: [
      // The decision-only tree, which the document carries since P2: it has a
      // session (status, boot, end) and NO pnl — null, never zero.
      {
        symbol: 'A05612',
        tree_id: 'cp3-setup-d-long',
        kind: 'futures',
        direction: 'LONG',
        decision_only: true,
        session: {
          name: 'long-20261125',
          status: 'ENDED',
          boot_at: '08:46:08',
          end_at: '15:50:01',
          run_rc: 0,
        },
        buy: { fills: null, quantity: null, last: null },
        sell: { fills: null, quantity: null, last: null },
        holding: { quantity: null, lots: null, basis: 'TOS_LEDGER_FIFO_OPEN_LOTS' },
        pnl: null,
        halt: {
          error: null,
          last_flow: { reason: 'STAGE_DENIED', step: 'CANDIDATE_COMMAND_CONSTRUCTION', time_kst: '15:33' },
          last_withheld: { reason: 'TIME_NOT_ADMITTED', step: 'DECISION_WITHHELD', time_kst: '08:45' },
          flow_counts: { STAGE_DENIED: 36, STAGE_UNKNOWN: 1 },
        },
        ticks: 409,
        error: null,
      },
      {
        symbol: '005930',
        tree_id: 'cp3-setup-d-stock-005930',
        kind: 'stock',
        direction: 'LONG',
        decision_only: false,
        session: {
          name: 'stock-r1-20261125',
          status: 'ENDED',
          boot_at: '09:01:09',
          end_at: '15:40:01',
          run_rc: 0,
        },
        buy: {
          fills: 1,
          quantity: '1',
          last: {
            quantity: '1',
            order_price_krw: '175600',
            execution_price_krw: '175550',
            price_basis: 'EXECUTION',
            broker_execution_id: '0000007244',
            time_kst: '09:15',
            time_basis: 'ORDER_BAR',
          },
        },
        sell: {
          fills: 1,
          quantity: '1',
          last: {
            quantity: '1',
            order_price_krw: '171500',
            execution_price_krw: '171500',
            price_basis: 'EXECUTION',
            broker_execution_id: '0000028973',
            time_kst: '15:15',
            time_basis: 'ORDER_BAR',
          },
        },
        holding: { quantity: '0', lots: 0, basis: 'TOS_LEDGER_FIFO_OPEN_LOTS' },
        // The figures `tools/tos_cp3/perf.py` produced for 2026-11-25: one
        // round trip that lost 4,050원, and one order from two days earlier
        // the FIFO could not account for — which is NOT in either figure.
        pnl: {
          today: {
            pnl_krw: '-4050',
            pnl_basis: 'EXECUTION',
            closed_round_trips: 1,
            wins: 0,
            buy_fills: 1,
            sell_fills: 1,
            quantity_bought: '1',
            quantity_sold: '1',
          },
          cumulative: {
            pnl_krw: '-3150',
            pnl_basis: 'EXECUTION',
            closed_round_trips: 4,
            wins: 2,
            buy_fills: 4,
            sell_fills: 4,
            quantity_bought: '4',
            quantity_sold: '4',
            open_quantity: '0',
            open_lots: 0,
          },
          unresolved: {
            count: 1,
            attempts: [
              {
                status: 'NO_FILL',
                status_label: '비체결 종료',
                side: 'BUY',
                quantity: '1',
                order_price_krw: '175800',
                broker_execution_id: null,
                trading_date: '20261123',
                reason: '미접수(마지막 결과 UNKNOWN → 재조회로 확인)',
                observation: '전송되지 않음(체결 없음)',
              },
            ],
          },
        },
        halt: {
          error: null,
          last_flow: { reason: 'STAGE_DENIED', step: 'CANDIDATE_COMMAND_CONSTRUCTION', time_kst: '15:18' },
          last_withheld: { reason: 'TIME_NOT_ADMITTED', step: 'DECISION_WITHHELD', time_kst: '15:30' },
          flow_counts: { STAGE_DENIED: 19, STAGE_UNKNOWN: 315 },
        },
        ticks: 380,
        error: null,
      },
      // A second trading tree, so a totals row has something to add up.
      {
        symbol: '000660',
        tree_id: 'cp3-setup-d-stock-000660',
        kind: 'stock',
        direction: 'LONG',
        decision_only: false,
        session: {
          name: 'stock-000660-r1-20261125',
          status: 'ENDED',
          boot_at: '09:02:18',
          end_at: '15:40:01',
          run_rc: 0,
        },
        buy: { fills: 1, quantity: '1', last: null },
        sell: { fills: 1, quantity: '1', last: null },
        holding: { quantity: '0', lots: 0, basis: 'TOS_LEDGER_FIFO_OPEN_LOTS' },
        pnl: {
          today: {
            pnl_krw: '-19000',
            pnl_basis: 'EXECUTION',
            closed_round_trips: 1,
            wins: 0,
          },
          cumulative: {
            pnl_krw: '-4000',
            pnl_basis: 'EXECUTION',
            closed_round_trips: 2,
            wins: 1,
            open_quantity: '0',
            open_lots: 0,
          },
          unresolved: { count: 0, attempts: [] },
        },
        halt: {
          error: null,
          last_flow: { reason: 'STAGE_DENIED', step: 'CANDIDATE_COMMAND_CONSTRUCTION', time_kst: '15:18' },
          last_withheld: null,
          flow_counts: { STAGE_DENIED: 6, STAGE_UNKNOWN: 1 },
        },
        ticks: 379,
        error: null,
      },
    ],
  };
}

/**
 * The one-page status board, as `status/board.json` carries it.
 *
 * The issue sentences are the exporter's own, verbatim: the page prints them
 * unchanged, so a paraphrase here would let their wording drift untested. The
 * counts are the ones the exporter took from this very list — the strip must
 * never recount them itself.
 */
export function statusDocument(): TosStatusDocument {
  return {
    schema_version: 1,
    date: '2026-11-25',
    generated_kst: '2026-11-25T15:55:10+09:00',
    levels: { blocked: '막힘', check: '확인' },
    blocked: 0,
    checks: 2,
    tenants: [
      {
        name: 'long-20261125',
        label: 'long',
        tree_id: 'cp3-setup-d-long',
        market: 'futures',
        direction: 'LONG',
        instrument: 'A05612',
        status: 'ENDED',
        run_alive: false,
        producer_alive: false,
        boot_at: '08:46:08',
        end_at: '15:50:01',
        run_rc: 0,
        producer_rc: 0,
        ticks: 409,
        issues: [
          {
            level: '확인',
            text: 'MARKETFEED_PASS_OVERRUN 1행 — 최악 pass 1232ms > 창 500ms (tick 1232ms + post-pass 0ms, seq 77038)',
          },
        ],
      },
      {
        name: 'stock-r1-20261125',
        label: 'stock-r1',
        tree_id: 'cp3-setup-d-stock-005930',
        market: 'stock',
        direction: 'LONG',
        instrument: '005930',
        status: 'ENDED',
        run_alive: false,
        producer_alive: false,
        boot_at: '09:01:09',
        end_at: '15:40:01',
        run_rc: 0,
        producer_rc: 0,
        ticks: 380,
        issues: [
          { level: '확인', text: 'APPROVAL_STANDING_NOT_COVERED 1행 (open_over_outstanding_reservation 1)' },
        ],
      },
    ],
    clean_streak: [
      {
        label: 'long',
        days: 5,
        target_days: 5,
        window_days: 40,
        met: true,
        start: '2026-11-19',
        window_start: '2026-11-19',
        pending: null,
        broke_on: null,
        broke_reason: null,
        calendar_version: 'krx-2026.11',
        error: null,
      },
    ],
    paper: {
      session: '2026-11-25-084505-LONG',
      live_check: false,
      runtime_alive: false,
      driver_alive: false,
      boot_ok: true,
      report: {
        verdict: 'ok',
        exit_code: 0,
        stop_reason: 'signal',
        started_kst: '2026-11-25T08:45:05+09:00',
        ended_kst: '2026-11-25T15:45:02+09:00',
        events_consumed: 5018,
        stale_withheld: 1,
        stale_ratio: 0.0002,
      },
      issues: [],
    },
    issues: [
      {
        level: '확인',
        where: 'long-20261125',
        text: 'MARKETFEED_PASS_OVERRUN 1행 — 최악 pass 1232ms > 창 500ms (tick 1232ms + post-pass 0ms, seq 77038)',
      },
      {
        level: '확인',
        where: 'stock-r1-20261125',
        text: 'APPROVAL_STANDING_NOT_COVERED 1행 (open_over_outstanding_reservation 1)',
      },
    ],
  };
}
