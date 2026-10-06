import { describe, expect, it } from 'vitest';
import {
  isAcceptedProjection, projectionAcceptance, projectionAge, projectionState,
  SUPPORTED_SCHEMA_VERSION, type TosProjection, type TosProjectionResponse,
} from './tos';
import { reasonPrefixes, tosFixture } from '@/test/tosFixture';
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
    ['schema mismatch at driver: ValidationError', 'invalid'],
    ['unsupported schema_version (expected 1, got str)', 'unsupported'],
    // A file that could not be opened is a path/permission fault, not malformed data.
    ['cannot read projection: PermissionError', 'unreadable'],
    ['cannot read projection: IsADirectoryError', 'unreadable'],
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

describe('single acceptance predicate', () => {
  // The banner (projectionState) and the page (whether fact cards render) must
  // never disagree. Both read projectionAcceptance; these cases pin the mapping.
  it.each([
    [populated, 'accepted', 'recent'],
    [{ ...populated, schema_version: SUPPORTED_SCHEMA_VERSION + 1 }, 'unsupported', 'unsupported'],
    [{ ...populated, non_authorizing: false }, 'invalid', 'invalid'],
    [null, 'invalid', 'invalid'],
  ] as const)('maps %#', (projection, acceptance, state) => {
    expect(projectionAcceptance(projection)).toBe(acceptance);
    expect(isAcceptedProjection(projection)).toBe(acceptance === 'accepted');
    expect(projectionState({ ...response, projection }, 0, false)).toBe(state);
  });
});

describe('shared reason prefixes', () => {
  // tests/fixtures/tos/projection-reasons.json — the same list the Python
  // tests assert the route emits. A prefix added on one side without the
  // other fails here.
  it.each(reasonPrefixes())('maps $prefix to $ui_state', ({ prefix, ui_state }) => {
    const unavailable: TosProjectionResponse = {
      available: false, reason: `${prefix}: detail`, age_seconds: null, projection: null,
    };
    expect(projectionState(unavailable, null, false)).toBe(ui_state);
  });
  it('still reports an unrecognised reason as unknown, never as clearance', () => {
    const unavailable: TosProjectionResponse = {
      available: false, reason: 'something new from a future route', age_seconds: null, projection: null,
    };
    expect(projectionState(unavailable, null, false)).toBe('unknown');
  });
});

describe('producer wire contract', () => {
  it('carries the six-key protective verdict the runtime emits', () => {
    // tos/runtime/src/tos_runtime/compose/_operations_wiring.py::_read_protective
    const verdict = {
      derestriction_admissible: false, capacity_exhausted: null, classification: null,
      unevaluated: ['capacity_exhausted'], reasons: ['derestriction_admissible'],
      protective_classification_digest: 'sha256:0f1e2d3c',
    };
    const projection: TosProjection = { ...populated, protective: { last_verdict: verdict } };
    expect(projectionState({ ...response, projection }, 0, false)).toBe('recent');
    expect(projection.protective?.last_verdict?.reasons).toEqual(['derestriction_admissible']);
    expect(populated.protective?.last_verdict?.protective_classification_digest).toBe('sha256:0f1e2d3c');
  });
  it('reads the four digest leaves added in round 1', () => {
    // 지적 9 regression: `process_nonce`, `code_digest`, `chain_digest` and
    // `manifest_digest` were missing from the TS interface while the header
    // claimed the Python DTO as the wire contract. This is those four by name,
    // not a property — full DTO-to-TS leaf parity is checked in
    // tests/unit/dashboard/test_tos_projection.py, which CI runs (there is no
    // node job, so a type-level omission here would not fail CI).
    const projection: TosProjection = populated;
    expect(projection.runtime?.process_nonce).toBe('abc123');
    expect(projection.runtime?.code_digest).toBe('sha256:deadbeef');
    expect(projection.evidence?.chain_digest).toBeNull();
    expect(projection.operations?.last_backup?.manifest_digest).toBeNull();
  });
  it('accepts null reason lists, null inner facts, and a null store schema version', () => {
    const projection: TosProjection = {
      ...populated,
      recovery: { readiness_verdict: 'READY', reasons: null },
      safety_mesh: { snapshot_generation: null, services: null },
      currentness: { pending_dimensions: null, last_assemble_complete: null },
      operations: {
        schema_versions: { evidence: 1, rcl: null, inbox: null },
        last_backup: null, key_continuity: null, dependency_admission: null,
      },
    };
    expect(projectionState({ ...response, projection }, 0, false)).toBe('recent');
    expect(projection.recovery?.reasons).toBeNull();
  });
});
