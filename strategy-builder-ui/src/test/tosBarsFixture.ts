import type { TosBarsBar, TosBarsDocument, TosBarsRule } from '@/lib/dashboard/tosBars';
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

type Env = Record<string, boolean | number | string>;

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
      {
        symbol: '005930',
        tree_id: 'cp3-setup-d-stock-005930',
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
        halt: {
          error: null,
          last_flow: { reason: 'STAGE_DENIED', step: 'CANDIDATE_COMMAND_CONSTRUCTION', time_kst: '15:18' },
          last_withheld: { reason: 'TIME_NOT_ADMITTED', step: 'DECISION_WITHHELD', time_kst: '15:30' },
          flow_counts: { STAGE_DENIED: 19, STAGE_UNKNOWN: 315 },
        },
        ticks: 380,
        error: null,
      },
    ],
  };
}
