import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  SUPPORTED_STATUS_SCHEMA_VERSION,
  boardVerdict,
  isAcceptedStatusDocument,
  statusState,
  type TosStatusDocument,
  type TosStatusResponse,
} from './tosStatus';

// The Python side asserts this same file (tests/unit/dashboard/test_tos_status.py).
// A prefix added there without a branch in `statusState` fails HERE rather than
// landing in the strip as 'unknown'.
const fixturePath = join(
  __dirname, '..', '..', '..', '..', 'tests', 'fixtures', 'tos', 'status-reasons.json',
);
const reasons: { reasons: { prefix: string; ui_state: string }[] } = JSON.parse(
  readFileSync(fixturePath, 'utf-8'),
);

function response(overrides: Partial<TosStatusResponse> = {}): TosStatusResponse {
  return { available: false, reason: null, age_seconds: null, document: null, ...overrides };
}

function document(overrides: Partial<TosStatusDocument> = {}): TosStatusDocument {
  return { schema_version: SUPPORTED_STATUS_SCHEMA_VERSION, tenants: [], ...overrides };
}

describe('status reason prefixes', () => {
  it('maps every prefix the API can emit, exactly as the shared fixture declares', () => {
    for (const { prefix, ui_state } of reasons.reasons) {
      expect(statusState(response({ reason: `${prefix}: something` }), false)).toBe(ui_state);
    }
  });

  it('guards the harvest itself so the loop above cannot be vacuous', () => {
    expect(reasons.reasons.map((entry) => entry.prefix)).toContain('status document absent');
    expect(reasons.reasons.length).toBeGreaterThanOrEqual(5);
  });

  it('names a different document than the symbols reader does', () => {
    // An operator told "the symbols document is missing" when the status board
    // is the one missing would go and look at the wrong exporter.
    const prefixes = reasons.reasons.map((entry) => entry.prefix);
    expect(prefixes).not.toContain('symbols document absent');
  });

  it('falls back to unknown for a reason nobody declared', () => {
    expect(statusState(response({ reason: 'a brand new refusal' }), false)).toBe('unknown');
  });
});

describe('statusState', () => {
  it('is loading before the first response and error when the connection failed', () => {
    expect(statusState(undefined, false)).toBe('loading');
    expect(statusState(undefined, true)).toBe('error');
    // A connection failure wins over a cached body: what is on screen is
    // last-known, not current — and this strip's whole job is "is it OK NOW".
    expect(statusState(response({ available: true, document: document() }), true)).toBe('error');
  });

  it('is ready only for an accepted document', () => {
    expect(statusState(response({ available: true, document: document() }), false)).toBe('ready');
    expect(statusState(response({ available: true, document: null }), false)).toBe('invalid');
  });

  it('refuses a version it does not understand even when the body says available', () => {
    const future = document({ schema_version: SUPPORTED_STATUS_SCHEMA_VERSION + 1 });
    expect(statusState(response({ available: true, document: future }), false)).toBe('invalid');
  });
});

describe('isAcceptedStatusDocument', () => {
  it('requires the tenant list to be an array, not merely present', () => {
    expect(isAcceptedStatusDocument(document())).toBe(true);
    expect(isAcceptedStatusDocument(document({ tenants: null }))).toBe(false);
    expect(isAcceptedStatusDocument(null)).toBe(false);
    expect(isAcceptedStatusDocument(undefined)).toBe(false);
  });

  it('accepts a day on which no tenant ran — an empty list is a fact', () => {
    // "Nothing ran" is exactly what the strip must be able to show; treating it
    // as an unusable document would blank the one panel that says so.
    expect(isAcceptedStatusDocument(document({ tenants: [] }))).toBe(true);
  });
});

describe('boardVerdict', () => {
  it('reads the counts the exporter already took', () => {
    expect(boardVerdict(document({ blocked: 0, checks: 0 }))).toBe('clear');
    expect(boardVerdict(document({ blocked: 0, checks: 11 }))).toBe('check');
    expect(boardVerdict(document({ blocked: 2, checks: 11 }))).toBe('blocked');
  });

  it('lets a block win over any number of checks', () => {
    expect(boardVerdict(document({ blocked: 1, checks: 0 }))).toBe('blocked');
  });

  it('is unknown — never clear — when the counts are missing', () => {
    // A board that could not be counted must not render as "all good": that is
    // the reading that would let a stopped exporter pass for a healthy day.
    expect(boardVerdict(document())).toBe('unknown');
    expect(boardVerdict(document({ blocked: 0, checks: null }))).toBe('unknown');
    expect(boardVerdict(null)).toBe('unknown');
  });
});
