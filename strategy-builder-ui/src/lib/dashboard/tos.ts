import { apiClient } from './client';
import displayConfig from '@/config/tos-control-plane.json';

// Wire contract: services/dashboard/routes/tos_projection.py. Every leaf of that
// DTO is declared here, so a field the page does not render today is still
// visible as part of the contract. That parity is checked by walking the DTO in
// tests/unit/dashboard/test_tos_projection.py
// (test_every_dto_leaf_name_appears_in_the_ts_contract) — on the Python side
// because that is the side CI runs; this repository has no node job. Entire
// groups may be null when the runtime has no source. Never turn absence into
// clearance.
export interface TosProjection {
  schema_version: number;
  projection_generation: number;
  exported_at_monotonic_ns: number;
  non_authorizing: boolean;
  runtime?: {
    cell_id?: string | null; runtime_generation?: number | null;
    process_nonce?: string | null; code_digest?: string | null;
  } | null;
  // `reasons` is `null` when the runtime had no source for the list. That is not
  // the same fact as `[]` (evaluated, nothing to report) — never render it as 「없음」.
  recovery?: { readiness_verdict?: string | null; reasons?: string[] | null } | null;
  driver?: { wired?: boolean | null; halt_latched?: boolean | null; halt_reason?: string | null } | null;
  time?: { health?: string | null } | null;
  safety_mesh?: {
    snapshot_generation?: number | null;
    services?: Record<string, { clear?: boolean | null; reasons?: string[] | null }> | null;
  } | null;
  currentness?: { pending_dimensions?: string[] | null; last_assemble_complete?: boolean | null } | null;
  rcl?: { last_seq?: number | null; open_reservations?: number | null } | null;
  inbox?: { unconsumed_count?: number | null } | null;
  evidence?: {
    tip_seq_excluding_stm_alert?: number | null; chain_digest?: string | null;
    key_generation?: number | null;
  } | null;
  release?: { admitted?: boolean | null; software_deployment_ok?: boolean | null } | null;
  // Producer: tos/runtime/src/tos_runtime/compose/_operations_wiring.py::_read_protective
  // emits this six-key object (or null), never a string.
  protective?: { last_verdict?: TosProtectiveVerdict | null } | null;
  operations?: {
    schema_versions?: Record<string, number | null> | null;
    last_backup?: {
      generation?: number | null; age_monotonic_ns?: number | null;
      manifest_digest?: string | null;
    } | null;
    key_continuity?: string | null;
    dependency_admission?: boolean | null;
  } | null;
  alerts?: { unresolved_stm_alert_seqs?: number[] | null; delivery_owner?: string | null } | null;
  export?: { failures?: number | null; last_error?: string | null } | null;
}

export interface TosProtectiveVerdict {
  derestriction_admissible?: boolean | null;
  capacity_exhausted?: boolean | null;
  classification?: string | null;
  unevaluated?: string[] | null;
  reasons?: string[] | null;
  protective_classification_digest?: string | null;
}

export interface TosProjectionResponse {
  available: boolean;
  reason: string | null;
  age_seconds: number | null;
  projection: TosProjection | null;
  // The API does not return the projection's filesystem path: it is a server-side
  // deployment detail (services/dashboard/routes/tos_projection.py).
}

export type ProjectionState =
  | 'loading' | 'error' | 'missing' | 'unreadable' | 'invalid' | 'unsupported' | 'unknown' | 'stale' | 'recent';

export const SUPPORTED_SCHEMA_VERSION = 1;

export type ProjectionAcceptance = 'accepted' | 'unsupported' | 'invalid';

/**
 * The single acceptance predicate for a projection document.
 *
 * `projectionState` (the banner) and the page (whether the fact cards render at
 * all) must never disagree about what counts as a usable document: two copies of
 * the same condition means raising the supported version in one place silently
 * blanks or silently renders the other. Both call this.
 */
export function projectionAcceptance(projection: TosProjection | null | undefined): ProjectionAcceptance {
  if (!projection) return 'invalid';
  if (projection.schema_version !== SUPPORTED_SCHEMA_VERSION) return 'unsupported';
  if (projection.non_authorizing !== true) return 'invalid';
  return 'accepted';
}

export function isAcceptedProjection(projection: TosProjection | null | undefined): projection is TosProjection {
  return projectionAcceptance(projection) === 'accepted';
}

export function projectionAge(ageSeconds: number | null | undefined, elapsedMs = 0): number | null {
  if (ageSeconds == null || !Number.isFinite(ageSeconds) || ageSeconds < 0) return null;
  return ageSeconds + Math.max(0, elapsedMs) / 1000;
}

export function projectionState(
  response: TosProjectionResponse | undefined,
  ageSeconds: number | null,
  connectionFailed: boolean,
): ProjectionState {
  if (connectionFailed) return 'error';
  if (!response) return 'loading';
  if (!response.available) {
    // Prefix match like every other branch: the shared fixture
    // (tests/fixtures/tos/projection-reasons.json) declares these as prefixes,
    // and the Python side only guarantees each reason *starts with* one.
    if (response.reason?.startsWith('projection file absent')) return 'missing';
    // Not a data-format problem: the file could not be opened at all
    // (permissions, uid mismatch, a directory in its place). Pointing the
    // operator at the exporter's output would be the wrong instruction.
    if (response.reason?.startsWith('cannot read projection')) return 'unreadable';
    if (response.reason?.startsWith('unsupported schema_version')) return 'unsupported';
    if (response.reason?.startsWith('invalid json') || response.reason?.startsWith('schema mismatch')) return 'invalid';
    return 'unknown';
  }
  const acceptance = projectionAcceptance(response.projection);
  if (acceptance !== 'accepted') return acceptance;
  if (ageSeconds === null) return 'unknown';
  return ageSeconds >= displayConfig.staleAfterSeconds ? 'stale' : 'recent';
}

export const tosApi = {
  getProjection: async () => {
    // Browser monotonic elapsed time ages a cached snapshot even if requests fail.
    // Conservatively include request latency; never subtract runtime monotonic
    // time from either browser time or a wall-clock timestamp.
    const requestedAt = performance.now();
    const { data } = await apiClient.get<TosProjectionResponse>('/api/tos/projection');
    return { response: data, requestedAt };
  },
};
