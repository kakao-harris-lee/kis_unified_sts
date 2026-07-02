import { apiClient } from './client';

export interface CoverageSource {
  name: string;
  key: string | null;
  available: boolean;
  count: number | null;
  updated_at: string | null;
  symbols: string[];
  names?: Record<string, string>;
  missing_symbols: string[];
  metadata: Record<string, unknown>;
}

export interface ExperimentCoverageRow {
  symbol: string;
  name?: string | null;
  loaded: boolean;
  rows: number | null;
  start: string | null;
  end: string | null;
  error: string | null;
}

export interface CoverageResponse {
  asset_class: 'stock' | 'futures' | 'all';
  generated_at: string;
  sources: CoverageSource[];
  experiment_coverage: ExperimentCoverageRow[];
  missing_evidence: string[];
  notes: string[];
}

export const coverageApi = {
  getCoverage: (params?: { asset_class?: string }) =>
    apiClient.get<CoverageResponse>('/api/coverage', { params }),
};
