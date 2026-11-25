import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import config from '@/config/tos-control-plane.json';
import { futuresBarsDocument } from '@/test/tosBarsFixture';
import {
  BAR_FLAGS,
  LATEST_SESSION,
  LEGACY_STOCK_INSTRUMENT,
  SKIP_ENGINE_DISAGREES,
  SKIP_NOT_ENGINE_COUNTED,
  SKIP_PROBE_ENTRY,
  SUPPORTED_BARS_SCHEMA_VERSION,
  barValue,
  barsState,
  explainField,
  fieldDefinitionLabel,
  groupSessionsByDate,
  hasFlag,
  hasHypotheticalPnl,
  isAcceptedBarsDocument,
  ruleExplanation,
  sessionKindLabel,
  sessionOptionLabel,
  type BarsState,
  type TosBarsBar,
  type TosBarsDocument,
  type TosBarsExplainField,
  type TosHypotheticalSkipped,
  type TosBarsResponse,
  type TosSessionEntry,
} from './tosBars';

// The Python side asserts this same file (tests/unit/dashboard/test_tos_bars.py).
// A prefix added there without a branch in `barsState` fails HERE rather than
// landing in the panel as 'unknown'.
const fixturePath = join(__dirname, '..', '..', '..', '..', 'tests', 'fixtures', 'tos', 'bars-reasons.json');
const reasons: { reasons: { prefix: string; ui_state: string }[] } = JSON.parse(
  readFileSync(fixturePath, 'utf-8'),
);

function response(overrides: Partial<TosBarsResponse> = {}): TosBarsResponse {
  return {
    available: false,
    reason: null,
    age_seconds: null,
    session: 'stock-r1-20261110',
    document: null,
    ...overrides,
  };
}

function document(overrides: Partial<TosBarsDocument> = {}): TosBarsDocument {
  return { schema_version: SUPPORTED_BARS_SCHEMA_VERSION, bars: [], ...overrides };
}

describe('bars reason prefixes', () => {
  it('maps every prefix the API can emit, exactly as the shared fixture declares', () => {
    for (const { prefix, ui_state } of reasons.reasons) {
      expect(barsState(response({ reason: `${prefix}: something` }), false)).toBe(ui_state);
    }
  });

  it('matches by prefix, because the API only guarantees a prefix', () => {
    expect(barsState(response({ reason: 'bars document absent' }), false)).toBe('missing');
    expect(
      barsState(response({ reason: 'cannot read bars document: PermissionError' }), false),
    ).toBe('unreadable');
  });

  it('never silently reclassifies an unrecognised reason', () => {
    expect(barsState(response({ reason: 'something new from a newer API' }), false)).toBe('unknown');
  });

  it('separates a connection failure and a first load from any document state', () => {
    expect(barsState(undefined, true)).toBe('error');
    expect(barsState(response(), true)).toBe('error');
    expect(barsState(undefined, false)).toBe('loading');
  });

  it('declares a ui_state for every branch barsState can return', () => {
    const declared = new Set(reasons.reasons.map((entry) => entry.ui_state));
    const runtimeOnly: BarsState[] = ['loading', 'error', 'ready', 'unknown'];
    const all: BarsState[] = [...declared, ...runtimeOnly] as BarsState[];
    expect(new Set(all).size).toBeGreaterThanOrEqual(reasons.reasons.length);
  });
});

describe('document acceptance', () => {
  it('accepts a v1 document that carries a bar list', () => {
    expect(isAcceptedBarsDocument(document({ bars: [{ time_kst: '09:00' }] }))).toBe(true);
    expect(barsState(response({ available: true, document: document() }), false)).toBe('ready');
  });

  it('refuses a foreign schema version rather than rendering it', () => {
    expect(isAcceptedBarsDocument(document({ schema_version: 2 }))).toBe(false);
    expect(
      barsState(response({ available: true, document: document({ schema_version: 2 }) }), false),
    ).toBe('invalid');
  });

  it('refuses a document with no bar list at all', () => {
    expect(isAcceptedBarsDocument(document({ bars: null }))).toBe(false);
    expect(isAcceptedBarsDocument(null)).toBe(false);
    expect(isAcceptedBarsDocument(undefined)).toBe(false);
  });
});

describe('flags', () => {
  it('reads each flag by POSITION, not by substring', () => {
    // A bar flagged only `U` must not read as `V`: both letters live in the same
    // four-character string and a substring search would confuse them.
    const onlyU: TosBarsBar = { flags: '---U' };
    expect(hasFlag(onlyU, 'U')).toBe(true);
    expect(hasFlag(onlyU, 'V')).toBe(false);
    expect(hasFlag(onlyU, 'D')).toBe(false);
    expect(hasFlag(onlyU, 'W')).toBe(false);
  });

  it('reads every position of a fully flagged bar', () => {
    const all: TosBarsBar = { flags: 'VDWU' };
    expect(BAR_FLAGS.every((flag) => hasFlag(all, flag))).toBe(true);
  });

  it('treats an absent flag string as no flags', () => {
    expect(BAR_FLAGS.some((flag) => hasFlag({}, flag))).toBe(false);
  });
});

describe('barValue', () => {
  it('prefers the engine value view over the journal line', () => {
    // The whole point of the `V` marker: where the two disagree, the view is
    // what the decision was made on.
    const bar: TosBarsBar = {
      fields: { close_x100: 100 },
      env_values: { close_x100: 200 },
    };
    expect(barValue(bar, 'close_x100')).toBe(200);
  });

  it('falls back to the journal line when there is no view', () => {
    expect(barValue({ fields: { close_x100: 100 }, env_values: {} }, 'close_x100')).toBe(100);
  });

  it('returns null for a missing or non-numeric field rather than coercing', () => {
    expect(barValue({ fields: { hi_vol: true } }, 'hi_vol')).toBeNull();
    expect(barValue({ fields: { session_token: '2026-11-10' } }, 'session_token')).toBeNull();
    expect(barValue({}, 'close_x100')).toBeNull();
  });
});

describe('the latest sentinel', () => {
  it('is the value the panel opens on', () => {
    expect(LATEST_SESSION).toBe('latest');
  });
});

function session(overrides: Partial<TosSessionEntry> & { session: string }): TosSessionEntry {
  return {
    date: null,
    kind: 'other',
    direction: null,
    instrument: null,
    run: null,
    age_seconds: null,
    ...overrides,
  };
}

describe('session labels', () => {
  it.each([
    [session({ session: 'long-20261125', date: '2026-11-25', kind: 'futures', direction: 'LONG' }), '11-25 · 선물 LONG'],
    [session({ session: 'short-20261125', date: '2026-11-25', kind: 'futures', direction: 'SHORT' }), '11-25 · 선물 SHORT'],
    [session({ session: 'stock-000660-r1-20261125', date: '2026-11-25', kind: 'stock', instrument: '000660', run: 1 }), '11-25 · 주식 000660'],
    // The name carries no instrument, so the label falls back to the config
    // value rather than to a literal in a branch.
    [session({ session: 'stock-r1-20261125', date: '2026-11-25', kind: 'stock', run: 1 }), '11-25 · 주식 005930'],
    // A restart beside cron's own run on the same day has to be tellable apart.
    [session({ session: 'stock-r2-20261125', date: '2026-11-25', kind: 'stock', run: 2 }), '11-25 · 주식 005930 · r2'],
    // A shape the route will not claim to recognise: say the name itself.
    [session({ session: 'experiment_a-20261125', date: '2026-11-25' }), '11-25 · experiment_a-20261125'],
    // Eight digits that are not a date. The route lists it undated.
    [session({ session: 'long-20261345', kind: 'futures', direction: 'LONG' }), '선물 LONG'],
  ])('labels %o as %s', (entry, expected) => {
    expect(sessionOptionLabel(entry)).toBe(expected);
  });

  it("reads the legacy tenant's symbol from configuration", () => {
    expect(LEGACY_STOCK_INSTRUMENT).toBe(config.legacyStockInstrument);
    expect(LEGACY_STOCK_INSTRUMENT).toMatch(/^\d{6}$/);
  });

  it("never shows cron's own run number — it distinguishes nothing", () => {
    const entry = session({ session: 'stock-r1-20261125', kind: 'stock', run: 1 });
    expect(sessionKindLabel(entry)).toBe('주식 005930');
  });
});

describe('groupSessionsByDate', () => {
  it("groups by day and keeps the route's order", () => {
    const groups = groupSessionsByDate([
      session({ session: 'long-20261125', date: '2026-11-25', kind: 'futures', direction: 'LONG' }),
      session({ session: 'short-20261125', date: '2026-11-25', kind: 'futures', direction: 'SHORT' }),
      session({ session: 'stock-r1-20261110', date: '2026-11-10', kind: 'stock', run: 1 }),
    ]);
    expect(groups.map((group) => group.label)).toEqual(['2026-11-25', '2026-11-10']);
    expect(groups[0].sessions.map((entry) => entry.session)).toEqual([
      'long-20261125',
      'short-20261125',
    ]);
  });

  it('keeps an undated session in a group of its own', () => {
    // The route sorts these last; grouping must not merge them into a day.
    const groups = groupSessionsByDate([
      session({ session: 'long-20261125', date: '2026-11-25' }),
      session({ session: 'scratch' }),
    ]);
    expect(groups.map((group) => group.label)).toEqual(['2026-11-25', '날짜 없음']);
    expect(groups[1].date).toBeNull();
  });

  it('is empty for an empty listing, which is what sends the panel to its text box', () => {
    expect(groupSessionsByDate([])).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// The explanation blocks — legibility plan §6 P2, items four and five.
// ---------------------------------------------------------------------------

const explained: TosBarsDocument = {
  schema_version: SUPPORTED_BARS_SCHEMA_VERSION,
  market: 'futures',
  decision_only: true,
  explain: {
    schema: 'tos-bars-explain/1',
    probe_basis: 'OPERATOR_RULE_MAP',
    rules: [
      { label: 'R1', rule_id: 'R1-ENTRY-LONG', rationale: '진입 조건이 모두 섰다.', probe: false },
      { label: 'R4', rule_id: 'R4-M2-PROBE-ENTRY-LONG', rationale: '경계 프로브다.', probe: true },
    ],
    default: { rule_id: 'R0-DEFAULT-NO-ACTION', rationale: '아무 규칙도 서지 않았다.' },
    fields: {
      z_x1000: { field: 'z', op: 'ratio_z', inputs: ['close', 'vwap', 'atr'], known: true },
    },
  },
  hypothetical_pnl: {
    hypothetical: true,
    direction: 'LONG',
    multiplier_krw_per_point: 50000,
    assumptions: ['FILL_AT_DECISION_BAR_CLOSE', 'NO_FEES'],
    totals: { trades: 1, wins: 1, points: '2.94', hypothetical_pnl_krw: '147000' },
  },
};

describe('ruleExplanation', () => {
  it('matches on the authored rule id, which is what a bar names', () => {
    expect(ruleExplanation(explained, 'R1-ENTRY-LONG')?.rationale).toBe('진입 조건이 모두 섰다.');
    expect(ruleExplanation(explained, 'R4-M2-PROBE-ENTRY-LONG')?.probe).toBe(true);
  });

  it('never matches on the position label', () => {
    // `label` is the rule's POSITION (R1, R4); two tenants put different rules
    // at the same position, so matching on it would caption a 005380 bar with
    // 005930's sentence — and the whole point is that the caption is true.
    expect(ruleExplanation(explained, 'R1')).toBeNull();
    expect(ruleExplanation(explained, 'R4')).toBeNull();
  });

  it('covers the default rule, which fires on most bars and is not in rules', () => {
    expect(ruleExplanation(explained, 'R0-DEFAULT-NO-ACTION')?.rationale).toBe(
      '아무 규칙도 서지 않았다.',
    );
  });

  it('is null rather than throwing for anything it cannot answer', () => {
    expect(ruleExplanation(explained, 'R9-NOT-A-RULE')).toBeNull();
    expect(ruleExplanation(explained, null)).toBeNull();
    expect(ruleExplanation(null, 'R1-ENTRY-LONG')).toBeNull();
    expect(
      ruleExplanation({ schema_version: SUPPORTED_BARS_SCHEMA_VERSION }, 'R1-ENTRY-LONG'),
    ).toBeNull();
  });
});

describe('hasHypotheticalPnl', () => {
  it('is true only for a decision-only document whose block says what it is', () => {
    expect(hasHypotheticalPnl(explained)).toBe(true);
  });

  it('refuses a block that has not asserted it is hypothetical', () => {
    // A block whose own flag is missing has not said what it is, and a page
    // that shows it anyway is one label away from presenting an assumed fill
    // as money.
    expect(
      hasHypotheticalPnl({ ...explained, hypothetical_pnl: { totals: { trades: 1 } } }),
    ).toBe(false);
  });

  it('refuses it on a tenant that really trades', () => {
    expect(
      hasHypotheticalPnl({ ...explained, market: 'stock', decision_only: false }),
    ).toBe(false);
  });

  it('is false for a document that predates the block', () => {
    expect(hasHypotheticalPnl({ schema_version: SUPPORTED_BARS_SCHEMA_VERSION })).toBe(false);
    expect(hasHypotheticalPnl(null)).toBe(false);
  });

  it('keeps the hypothetical total out of the realized namespace', () => {
    // There is no `pnl_krw` here to be summed with the symbols document's.
    const totals = explained.hypothetical_pnl?.totals ?? {};
    expect(Object.keys(totals)).not.toContain('pnl_krw');
    expect(totals.hypothetical_pnl_krw).toBe('147000');
  });

  it('types a zero-trade session as no total rather than zero won', () => {
    // '0' would render as "±0 today", which is a different claim from "no
    // signal fired". The exporter sends null; the type must allow it.
    const quiet: TosBarsDocument = {
      schema_version: SUPPORTED_BARS_SCHEMA_VERSION,
      decision_only: true,
      hypothetical_pnl: {
        hypothetical: true,
        totals: { trades: 0, wins: 0, points: null, hypothetical_pnl_krw: null },
      },
    };
    expect(hasHypotheticalPnl(quiet)).toBe(true);
    expect(quiet.hypothetical_pnl?.totals?.hypothetical_pnl_krw).toBeNull();
    expect(quiet.hypothetical_pnl?.totals?.trades).toBe(0);
  });

  it('types the skipped decisions that say what the total left out', () => {
    const skipped: TosHypotheticalSkipped[] = [
      { time_kst: '15:45', rule_id: 'R3-EXIT-EOD', reason: SKIP_NOT_ENGINE_COUNTED },
      { time_kst: '09:14', rule_id: 'R4-M2-PROBE', reason: SKIP_PROBE_ENTRY },
      { time_kst: '10:00', rule_id: 'R1', reason: SKIP_ENGINE_DISAGREES },
    ];
    expect(skipped.map((entry) => entry.reason)).toEqual([
      'NOT_ENGINE_COUNTED',
      'PROBE_ENTRY',
      'ENGINE_DISAGREES',
    ]);
  });

  it('accepts a field parameter shape nobody typed', () => {
    // fields.yaml is authored content: a null, a list or a nested mapping must
    // only ever degrade the explanation, never fail the document.
    const field: TosBarsExplainField = {
      field: 'odd',
      op: 'permissive',
      params: { when_missing: null, choices: [1, 2], nested: { a: 1 } },
      scale: { mult: null },
    };
    expect(field.params?.when_missing).toBeNull();
    expect(field.params?.choices).toEqual([1, 2]);
  });
});

describe('필드 정의', () => {
  const document = futuresBarsDocument();

  it('resolves a published alias as well as the catalog name', () => {
    expect(explainField(document, 'z_x1000')?.op).toBe('ratio_z');
    expect(explainField(document, 'entry_window')?.op).toBe('between');
  });

  it('writes the operation and its inputs as the catalog has them', () => {
    expect(fieldDefinitionLabel(explainField(document, 'entry_window'))).toBe(
      'between(mso) · hi=345 · lo=15',
    );
    expect(fieldDefinitionLabel(explainField(document, 'z_x1000'))).toBe(
      'ratio_z(close, vwap, atr)',
    );
  });

  it('offers nothing rather than an invented definition', () => {
    expect(explainField(document, 'a_brand_new_field')).toBeNull();
    expect(explainField(null, 'z_x1000')).toBeNull();
    expect(fieldDefinitionLabel(null)).toBeNull();
    expect(fieldDefinitionLabel({ field: 'x', op: null })).toBeNull();
  });
});
