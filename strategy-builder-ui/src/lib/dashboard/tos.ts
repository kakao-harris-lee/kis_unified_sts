import { apiClient } from './client';
import displayConfig from '@/config/tos-control-plane.json';

// Wire contract: services/dashboard/routes/tos_projection.py. Entire groups may
// be null when the runtime has no source. Never turn absence into clearance.
export interface TosProjection {
  schema_version: number;
  projection_generation: number;
  exported_at_monotonic_ns: number;
  non_authorizing: boolean;
  runtime?: { cell_id?: string | null; runtime_generation?: number | null } | null;
  recovery?: { readiness_verdict?: string | null; reasons?: string[] } | null;
  driver?: { wired?: boolean | null; halt_latched?: boolean | null; halt_reason?: string | null } | null;
  time?: { health?: string | null } | null;
  safety_mesh?: {
    snapshot_generation?: number | null;
    services?: Record<string, { clear?: boolean | null; reasons?: string[] }> | null;
  } | null;
  currentness?: { pending_dimensions?: string[] | null; last_assemble_complete?: boolean | null } | null;
  rcl?: { last_seq?: number | null; open_reservations?: number | null } | null;
  inbox?: { unconsumed_count?: number | null } | null;
  evidence?: { tip_seq_excluding_stm_alert?: number | null; key_generation?: number | null } | null;
  release?: { admitted?: boolean | null; software_deployment_ok?: boolean | null } | null;
  protective?: { last_verdict?: string | null } | null;
  operations?: {
    schema_versions?: Record<string, number> | null;
    last_backup?: { generation?: number | null; age_monotonic_ns?: number | null } | null;
    key_continuity?: string | null;
    dependency_admission?: boolean | null;
  } | null;
  alerts?: { unresolved_stm_alert_seqs?: number[] | null; delivery_owner?: string | null } | null;
  export?: { failures?: number | null; last_error?: string | null } | null;
}

export interface TosProjectionResponse {
  available: boolean;
  reason: string | null;
  age_seconds: number | null;
  projection: TosProjection | null;
  // The API also returns its filesystem path. It is intentionally not displayed.
}

export type ProjectionState = 'loading' | 'error' | 'missing' | 'invalid' | 'unsupported' | 'unknown' | 'stale' | 'recent';

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
    if (response.reason === 'projection file absent') return 'missing';
    if (response.reason?.startsWith('unsupported schema_version')) return 'unsupported';
    if (response.reason?.startsWith('invalid json') || response.reason?.startsWith('schema mismatch')) return 'invalid';
    return 'unknown';
  }
  if (!response.projection) return 'invalid';
  if (response.projection.schema_version !== 1) return 'unsupported';
  if (response.projection.non_authorizing !== true) return 'invalid';
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
