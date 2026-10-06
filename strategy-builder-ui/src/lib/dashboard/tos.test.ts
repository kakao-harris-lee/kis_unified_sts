import { describe, expect, it } from 'vitest';
import { projectionAge, projectionState, type TosProjectionResponse } from './tos';
import { tosFixture } from '@/test/tosFixture';
const populated = tosFixture();
const unknown = tosFixture(true);
import config from '@/config/tos-control-plane.json';

const response: TosProjectionResponse = { available: true, reason: null, age_seconds: 0, projection: populated };

describe('TOS observation state', () => {
  it('accepts the shared null fixture without manufacturing clearance', () => {
    const data: TosProjectionResponse = { ...response, projection: unknown };
    expect(projectionState(data, 0, false)).toBe('recent');
    expect(data.projection?.release).toBeNull();
    expect(data.projection?.alerts?.unresolved_stm_alert_seqs).toBeNull();
  });
  it.each([
    ['projection file absent', 'missing'], ['invalid json: bad', 'invalid'],
    ['schema mismatch at driver: error', 'invalid'], ['unsupported schema_version 2', 'unsupported'],
    [null, 'unknown'],
  ] as const)('distinguishes unavailable %s', (reason, state) => {
    expect(projectionState({ ...response, available: false, projection: null, reason }, null, false)).toBe(state);
  });
  it('ages cached snapshots and treats the exact threshold as stale', () => {
    expect(projectionState(response, config.staleAfterSeconds - 1, false)).toBe('recent');
    const age = projectionAge(config.staleAfterSeconds - 1, 1000);
    expect(projectionState(response, age, false)).toBe('stale');
    expect(projectionState(response, age, true)).toBe('error');
  });
  it('does not infer freshness from a missing or invalid age', () => {
    for (const age of [null, undefined, NaN, Infinity, -1]) expect(projectionAge(age)).toBeNull();
    expect(projectionState(response, null, false)).toBe('unknown');
  });
  it('refuses a missing projection or an authorizing/version-incompatible document', () => {
    expect(projectionState({ ...response, projection: null }, 0, false)).toBe('invalid');
    expect(projectionState({ ...response, projection: { ...populated, non_authorizing: false } }, 0, false)).toBe('invalid');
    expect(projectionState({ ...response, projection: { ...populated, schema_version: 2 } }, 0, false)).toBe('unsupported');
  });
});
