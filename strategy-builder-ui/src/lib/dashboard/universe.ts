import { apiClient } from './client';

export interface UniverseSource {
  name: string;
  key: string;
  available: boolean;
  count: number | null;
  updated_at: string | null;
  age_seconds: number | null;
  stale: boolean;
  source_keys: string[];
}

export interface UniverseOverrideDetail {
  reason?: string | null;
  created_at?: string | null;
  expires_at?: string | null;
  operator?: string | null;
  name?: string | null;
}

export interface UniverseRow {
  code: string;
  name?: string | null;
  active: boolean;
  new_entries_allowed: boolean;
  market_data_required: boolean;
  rank?: number | null;
  score?: number | null;
  sources: string[];
  daily_indicator: 'available' | 'missing' | 'unknown' | string;
  override?: 'manual_include' | 'manual_exclude' | null;
  override_detail?: UniverseOverrideDetail | null;
  blocked_reason?: string | null;
}

export interface UniverseResponse {
  asset_class: 'stock';
  generated_at: string;
  key: string;
  override_key: string;
  audit_key: string;
  ttl_seconds: number;
  codes: string[];
  market_data_codes: string[];
  max_symbols: number;
  rows: UniverseRow[];
  sources: UniverseSource[];
  overrides: {
    manual_include: Record<string, UniverseOverrideDetail>;
    manual_exclude: Record<string, UniverseOverrideDetail>;
    expired: Array<Record<string, unknown>>;
  };
  policy: Record<string, unknown>;
  source_keys: Record<string, string>;
  notes: string[];
}

export interface UniverseAuditResponse {
  key: string;
  generated_at: string;
  events: Array<Record<string, unknown>>;
}

export interface UniverseOverridePayload {
  action: 'include' | 'exclude' | 'remove';
  symbol: string;
  name?: string | null;
  reason?: string | null;
  ttl_seconds?: number | null;
  operator?: string | null;
}

export const universeApi = {
  getUniverse: (params?: { publish?: boolean }) =>
    apiClient.get<UniverseResponse>('/api/trading/universe', { params }),
  getSources: () =>
    apiClient.get<Pick<UniverseResponse, 'asset_class' | 'generated_at' | 'sources' | 'source_keys' | 'notes'>>(
      '/api/trading/universe/sources',
    ),
  getAudit: (params?: { limit?: number }) =>
    apiClient.get<UniverseAuditResponse>('/api/trading/universe/audit', { params }),
  recompute: () =>
    apiClient.post<UniverseResponse>('/api/trading/universe/recompute'),
  updateOverride: (payload: UniverseOverridePayload) =>
    apiClient.post<UniverseResponse>('/api/trading/universe/overrides', payload),
};
