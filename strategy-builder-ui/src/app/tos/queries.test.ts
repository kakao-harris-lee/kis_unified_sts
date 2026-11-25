import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { barsQueryOptions, isLiveSession } from './queries';
import type { TosSessionEntry } from '@/lib/dashboard/tosBars';
import type { TosSymbolRow } from '@/lib/dashboard/tosSymbols';
import config from '@/config/tos-control-plane.json';

function entry(overrides: Partial<TosSessionEntry> = {}): TosSessionEntry {
  return {
    session: 'stock-r1-20261125',
    date: '2026-11-25',
    kind: 'stock',
    direction: null,
    instrument: null,
    run: 1,
    age_seconds: 60,
    ...overrides,
  };
}

function row(status: string | null): TosSymbolRow {
  return {
    symbol: '005930',
    session: { name: 'stock-r1-20261125', status, boot_at: '09:01:09', end_at: null, run_rc: null },
  };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date('2026-11-25T02:00:00Z')); // 11:00 KST
});
afterEach(() => vi.useRealTimers());

describe('장중 갱신 대상인가', () => {
  it('polls today’s session while nothing says it has settled', () => {
    expect(isLiveSession(entry(), row('RUNNING'))).toBe(true);
    // No row yet: «the per-symbol export has not seen it» is not «it is over».
    expect(isLiveSession(entry(), null)).toBe(true);
  });

  it('stops the moment the row reports the session ended', () => {
    expect(isLiveSession(entry(), row('ENDED'))).toBe(false);
  });

  it('never polls another day’s session, however its row reads', () => {
    // Yesterday's document is final; polling it would re-read a megabyte a
    // minute for a file that cannot change.
    expect(isLiveSession(entry({ date: '2026-11-24' }), row('RUNNING'))).toBe(false);
    expect(isLiveSession(entry({ date: null }), row('RUNNING'))).toBe(false);
    expect(isLiveSession(null, row('RUNNING'))).toBe(false);
  });

  it('judges the day in KST, not in the viewer’s timezone', () => {
    // 2026-11-25 23:30 UTC is already the 26th in Seoul.
    const lateUtc = new Date('2026-11-25T23:30:00Z');
    expect(isLiveSession(entry(), row('RUNNING'), lateUtc)).toBe(false);
  });

  it('polls only when the caller says to, and at the configured interval', () => {
    expect(barsQueryOptions('stock-r1-20261125').refetchInterval).toBe(false);
    expect(barsQueryOptions('stock-r1-20261125', config.barsRefetchMs).refetchInterval).toBe(
      config.barsRefetchMs,
    );
  });
});
