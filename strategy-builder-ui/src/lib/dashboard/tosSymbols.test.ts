import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  SUPPORTED_SYMBOLS_SCHEMA_VERSION,
  TENANT_KIND_FUTURES,
  TENANT_KIND_STOCK,
  TOS_LEDGER_HOLDING_BASIS,
  isAcceptedSymbolsDocument,
  isTodaysDocument,
  kstToday,
  sessionPhase,
  symbolsState,
  type TosSymbolRow,
  type TosSymbolsDocument,
  type TosSymbolsResponse,
} from './tosSymbols';

// The Python side asserts this same file (tests/unit/dashboard/test_tos_symbols.py).
// A prefix added there without a branch in `symbolsState` fails HERE rather than
// landing in the panel as 'unknown'.
const fixturePath = join(
  __dirname, '..', '..', '..', '..', 'tests', 'fixtures', 'tos', 'symbols-reasons.json',
);
const reasons: { reasons: { prefix: string; ui_state: string }[] } = JSON.parse(
  readFileSync(fixturePath, 'utf-8'),
);

function response(overrides: Partial<TosSymbolsResponse> = {}): TosSymbolsResponse {
  return { available: false, reason: null, age_seconds: null, document: null, ...overrides };
}

function document(overrides: Partial<TosSymbolsDocument> = {}): TosSymbolsDocument {
  return { schema_version: SUPPORTED_SYMBOLS_SCHEMA_VERSION, symbols: [], ...overrides };
}

describe('symbols reason prefixes', () => {
  it('maps every prefix the API can emit, exactly as the shared fixture declares', () => {
    for (const { prefix, ui_state } of reasons.reasons) {
      expect(symbolsState(response({ reason: `${prefix}: something` }), false)).toBe(ui_state);
    }
  });

  it('guards the harvest itself so the loop above cannot be vacuous', () => {
    expect(reasons.reasons.map((entry) => entry.prefix)).toContain('symbols document absent');
    expect(reasons.reasons.length).toBeGreaterThanOrEqual(5);
  });

  it('falls back to unknown for a reason nobody declared', () => {
    expect(symbolsState(response({ reason: 'a brand new refusal' }), false)).toBe('unknown');
  });
});

describe('symbolsState', () => {
  it('is loading before the first response and error when the connection failed', () => {
    expect(symbolsState(undefined, false)).toBe('loading');
    expect(symbolsState(undefined, true)).toBe('error');
    // A connection failure wins over a cached body: the numbers on screen are
    // last-known, not current.
    expect(symbolsState(response({ available: true, document: document() }), true)).toBe('error');
  });

  it('is ready only for an accepted document', () => {
    expect(symbolsState(response({ available: true, document: document() }), false)).toBe('ready');
  });

  it('calls an available-but-unusable document invalid rather than ready', () => {
    // `available: true` with a document this reader cannot accept is the case
    // that would otherwise render a blank table under a green banner.
    expect(symbolsState(response({ available: true, document: null }), false)).toBe('invalid');
    expect(
      symbolsState(
        response({ available: true, document: { schema_version: 2, symbols: [] } }),
        false,
      ),
    ).toBe('invalid');
  });
});

describe('isAcceptedSymbolsDocument', () => {
  it('rejects a foreign version and a document with no symbols array', () => {
    expect(isAcceptedSymbolsDocument(document())).toBe(true);
    expect(isAcceptedSymbolsDocument({ schema_version: 2, symbols: [] })).toBe(false);
    expect(isAcceptedSymbolsDocument({ schema_version: 1 })).toBe(false);
    expect(isAcceptedSymbolsDocument({ schema_version: 1, symbols: null })).toBe(false);
    expect(isAcceptedSymbolsDocument(null)).toBe(false);
  });

  it('accepts an empty symbols array — zero tenants is a fact, not a fault', () => {
    expect(isAcceptedSymbolsDocument(document({ symbols: [] }))).toBe(true);
  });
});

describe('kstToday', () => {
  it('reads the KST day whatever zone the viewer sits in', () => {
    // 2026-11-22T20:00Z is already 2026-11-23 in Seoul (UTC+9). A viewer in
    // London must still see the Korean trading day, or last night's export
    // would read as today's.
    expect(kstToday(new Date('2026-11-22T20:00:00Z'))).toBe('2026-11-23');
    expect(kstToday(new Date('2026-11-22T14:59:00Z'))).toBe('2026-11-22');
  });
});

describe('isTodaysDocument', () => {
  const now = new Date('2026-11-22T06:00:00Z'); // 15:00 KST on 2026-11-22

  it('is true for the current KST trading day', () => {
    expect(isTodaysDocument(document({ date: '2026-11-22' }), now)).toBe(true);
  });

  it('is false for an earlier day, which is what a stopped exporter looks like', () => {
    expect(isTodaysDocument(document({ date: '2026-11-20' }), now)).toBe(false);
  });

  it('is null — not true — when the document names no date', () => {
    // Defaulting to "yes, this is today" is the reading that would let a
    // dateless document pass for live trading.
    expect(isTodaysDocument(document({ date: null }), now)).toBeNull();
    expect(isTodaysDocument(null, now)).toBeNull();
  });
});

describe('sessionPhase', () => {
  it('calls a null status "none" — no session ran today', () => {
    expect(sessionPhase(null)).toBe('none');
    expect(sessionPhase({ status: null })).toBe('none');
    expect(sessionPhase(undefined)).toBe('none');
  });

  it('separates running from settled', () => {
    expect(sessionPhase({ status: 'RUNNING' })).toBe('running');
    expect(sessionPhase({ status: 'PRE-BOOT' })).toBe('running');
    expect(sessionPhase({ status: 'ENDED' })).toBe('settled');
  });

  it('does not fold a bad ending into a clean one', () => {
    // FAILED/ABORT/LOST all stopped the session in a way the operator must look
    // at; calling them "ended" would hide exactly the day worth investigating.
    for (const status of ['FAILED', 'ABORT', 'LOST', 'NOT-BOOTED']) {
      expect(sessionPhase({ status })).toBe('unknown');
    }
  });
});

describe('the row shape the P2 export writes', () => {
  // Legibility plan §6 P2: the five tenants are two different things, and the
  // difference is carried by `decision_only` rather than by the page guessing
  // from `kind`.
  it('types a stock row with its realized PnL and its unresolved attempts', () => {
    const row: TosSymbolRow = {
      symbol: '005930',
      tree_id: 'cp3-setup-d-stock-005930',
      kind: TENANT_KIND_STOCK,
      direction: 'LONG',
      decision_only: false,
      pnl: {
        today: { pnl_krw: '-4050', pnl_basis: 'EXECUTION', closed_round_trips: 1, wins: 0 },
        cumulative: { pnl_krw: '-3150', open_lots: 0, open_quantity: '0' },
        unresolved: {
          count: 1,
          attempts: [
            { status_label: '비체결 종료', side: 'BUY', observation: '전송되지 않음(체결 없음)' },
          ],
        },
      },
    };
    expect(row.pnl?.today?.pnl_krw).toBe('-4050');
    expect(row.pnl?.unresolved?.attempts?.[0]?.status_label).toBe('비체결 종료');
  });

  it('types a decision-only row with nulls where a stock row has numbers', () => {
    // Null, never 0: the futures tenants cannot order at all (operator decision
    // 2026-11-05), which is a different fact from "ordered nothing today".
    const row: TosSymbolRow = {
      symbol: 'A05612',
      tree_id: 'cp3-setup-d-long',
      kind: TENANT_KIND_FUTURES,
      direction: 'LONG',
      decision_only: true,
      buy: { fills: null, quantity: null, last: null },
      holding: { quantity: null, lots: null, basis: TOS_LEDGER_HOLDING_BASIS },
      pnl: null,
      ticks: 409,
    };
    expect(row.decision_only).toBe(true);
    expect(row.buy?.fills).toBeNull();
    expect(row.pnl).toBeNull();
    expect(row.ticks).toBe(409);
  });

  it('still accepts a document whose rows predate the P2 fields', () => {
    // The exporter runs from a fresh origin/main worktree every morning while
    // the dashboard container is rebuilt by hand, so the two sides are out of
    // step for a while. An old document must render, not blank the panel.
    const legacy = document({ symbols: [{ symbol: '005930', ticks: 380 }] });
    expect(isAcceptedSymbolsDocument(legacy)).toBe(true);
    expect(legacy.symbols?.[0]?.kind).toBeUndefined();
  });
});
