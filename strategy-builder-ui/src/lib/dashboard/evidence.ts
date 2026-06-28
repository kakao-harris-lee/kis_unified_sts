import { apiClient } from './client';

export interface EvidenceGap {
  code: string;
  severity: string;
  message: string;
}

export interface StrategyEvidenceSummary {
  strategy: string;
  accepted: number;
  rejected: number;
  paperPnl?: number | null;
  backtestPaperDelta?: number | null;
  status: string;
}

export interface EvidenceSummaryResponse {
  asset_class: string;
  generated_at: string;
  strategies: StrategyEvidenceSummary[];
  evidence_gaps: EvidenceGap[];
}

export const evidenceApi = {
  getSummary: (assetClass: string) =>
    apiClient.get<EvidenceSummaryResponse>('/api/evidence/summary', {
      params: { asset_class: assetClass },
    }),
};
