import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  SUPPORTED_STATUS_SCHEMA_VERSION,
  boardVerdict,
  isAcceptedStatusDocument,
  orderedIssues,
  paperLiveness,
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
  // 2026-11-25 12:00 KST — the day the fixtures describe.
  const onTheDay = new Date('2026-11-25T03:00:00Z');
  const today = (overrides: Partial<TosStatusDocument> = {}) =>
    document({ date: '2026-11-25', ...overrides });

  it('reads the counts the exporter already took', () => {
    expect(boardVerdict(today({ blocked: 0, checks: 0 }), onTheDay)).toBe('clear');
    expect(boardVerdict(today({ blocked: 0, checks: 11 }), onTheDay)).toBe('check');
    expect(boardVerdict(today({ blocked: 2, checks: 11 }), onTheDay)).toBe('blocked');
  });

  it('lets a block win over any number of checks', () => {
    expect(boardVerdict(today({ blocked: 1, checks: 0 }), onTheDay)).toBe('blocked');
  });

  it('calls a board from another day stale, however clean it reads', () => {
    // The morning after a clean close, yesterday's document still says
    // "0 blocks". Rendering that as "clear" is exactly how a stopped exporter
    // passes for a healthy day — so staleness wins over the counts.
    const yesterday = document({ date: '2026-11-24', blocked: 0, checks: 0 });
    expect(boardVerdict(yesterday, onTheDay)).toBe('stale');

    const alsoStale = document({ date: '2026-11-24', blocked: 3, checks: 0 });
    expect(boardVerdict(alsoStale, onTheDay)).toBe('stale');
  });

  it('judges the day in KST, not in the viewer timezone', () => {
    // 2026-11-25 23:30 UTC is already 2026-11-26 in Seoul, so a 11-25 board is
    // stale for a viewer anywhere on earth.
    const lateUtc = new Date('2026-11-25T23:30:00Z');
    expect(boardVerdict(today({ blocked: 0, checks: 0 }), lateUtc)).toBe('stale');
    // …and 2026-11-24 15:30 UTC is already 11-25 in Seoul, so it is current.
    const earlyUtc = new Date('2026-11-24T15:30:00Z');
    expect(boardVerdict(today({ blocked: 0, checks: 0 }), earlyUtc)).toBe('clear');
  });

  it('is unknown — never clear — when the date or the counts are missing', () => {
    // A board that could not be counted must not render as "all good": that is
    // the reading that would let a stopped exporter pass for a healthy day.
    expect(boardVerdict(document(), onTheDay)).toBe('unknown');
    expect(boardVerdict(today(), onTheDay)).toBe('unknown');
    expect(boardVerdict(today({ blocked: 0, checks: null }), onTheDay)).toBe('unknown');
    expect(boardVerdict(null, onTheDay)).toBe('unknown');
  });
});

describe('이슈 정렬', () => {
  function board(issues: { level: string; text: string }[]): TosStatusDocument {
    return document({ levels: { blocked: '막힘', check: '확인' }, issues });
  }

  it('puts blocks before checks, using the board’s own level words', () => {
    const sorted = orderedIssues(
      board([
        { level: '확인', text: '두 번째' },
        { level: '막힘', text: '첫 번째' },
      ]),
    );
    expect(sorted.map((issue) => issue.text)).toEqual(['첫 번째', '두 번째']);
  });

  it('keeps the exporter’s order inside a level, so the page and the CLI agree', () => {
    const sorted = orderedIssues(
      board([
        { level: '확인', text: 'a' },
        { level: '확인', text: 'b' },
        { level: '확인', text: 'c' },
      ]),
    );
    expect(sorted.map((issue) => issue.text)).toEqual(['a', 'b', 'c']);
  });

  it('keeps a level it does not recognise, last rather than dropped', () => {
    const sorted = orderedIssues(
      board([
        { level: '미래등급', text: '모르는 등급' },
        { level: '막힘', text: '막힘' },
      ]),
    );
    expect(sorted.map((issue) => issue.text)).toEqual(['막힘', '모르는 등급']);
  });

  it('does not mutate the document it was given', () => {
    const original = board([
      { level: '확인', text: 'a' },
      { level: '막힘', text: 'b' },
    ]);
    orderedIssues(original);
    expect(original.issues?.map((issue) => issue.text)).toEqual(['a', 'b']);
  });

  it('is empty, not a throw, for a board with no issue list', () => {
    expect(orderedIssues(document())).toEqual([]);
    expect(orderedIssues(null)).toEqual([]);
  });
});

describe('상주 paper 판정', () => {
  it('separates «was not checked» from «was checked and is down»', () => {
    // The exporter reads /proc only for today. On any past date both flags are
    // false and say nothing at all, so reading them as «꺼짐» would report an
    // outage for every board older than this morning.
    expect(paperLiveness({ live_check: false, runtime_alive: false, driver_alive: false })).toBe(
      'not-checked',
    );
    expect(paperLiveness({ live_check: true, runtime_alive: false, driver_alive: false })).toBe(
      'stopped',
    );
  });

  it('needs both processes for «상주 중»', () => {
    expect(paperLiveness({ live_check: true, runtime_alive: true, driver_alive: true })).toBe(
      'alive',
    );
    expect(paperLiveness({ live_check: true, runtime_alive: true, driver_alive: false })).toBe(
      'partial',
    );
  });

  it('stays unknown when a flag is absent, rather than assuming it is down', () => {
    expect(paperLiveness({ live_check: true, runtime_alive: null, driver_alive: true })).toBe(
      'unknown',
    );
    expect(paperLiveness(null)).toBe('unknown');
  });
});
