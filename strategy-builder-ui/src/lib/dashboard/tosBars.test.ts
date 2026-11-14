import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  BAR_FLAGS,
  LATEST_SESSION,
  SUPPORTED_BARS_SCHEMA_VERSION,
  barValue,
  barsState,
  hasFlag,
  isAcceptedBarsDocument,
  type BarsState,
  type TosBarsBar,
  type TosBarsDocument,
  type TosBarsResponse,
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
