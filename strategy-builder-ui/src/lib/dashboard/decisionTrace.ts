import { apiClient } from './client';
import type { TradeLifecycleStep } from './trades';

export interface DecisionTraceEvidenceGap {
  code: string;
  severity: 'info' | 'warning' | 'error' | string;
  message: string;
}

export interface DecisionTraceSignal {
  id: string;
  asset_class: string;
  symbol: string;
  strategy: string;
  side: string;
  signal_type?: string | null;
  status?: string | null;
  reason?: string | null;
  confidence?: number | null;
  strength?: number | null;
  price?: number | null;
  timestamp?: string | null;
}

export interface DecisionTraceSummary {
  state: string;
  text: string;
  warnings: string[];
}

export interface DecisionTraceLlmContext {
  status: string;
  overall_signal?: string | null;
  confidence?: number | null;
  risk_mode?: string | null;
  regime?: string | null;
  risk_score?: number | null;
  captured_at?: string | null;
  source?: string | null;
}

export interface DecisionTraceStrategyInputs {
  setup_type?: string | null;
  indicators: Record<string, unknown>;
  thresholds: Record<string, unknown>;
  event_evidence: Record<string, unknown>;
  raw_reason?: string | null;
}

export interface DecisionTraceRiskOrderability {
  reject_stage?: string | null;
  reject_reason?: string | null;
  orderability_state?: string | null;
  orderability_details: Record<string, unknown>;
  risk_state?: string | null;
  risk_details: Record<string, unknown>;
}

export interface DecisionTraceLineage {
  signal_id?: string | null;
  order_id?: string | null;
  fill_id?: string | null;
  position_id?: string | null;
  trade_id?: string | null;
}

export interface DecisionTraceLifecycle {
  status: string;
  steps: TradeLifecycleStep[];
  warnings: string[];
}

export interface DecisionTraceScorecard {
  status: string;
  facet?: string | null;
  date_kst?: string | null;
  captured_at?: string | null;
  confidence?: number | null;
  correct?: boolean | null;
  value?: number | null;
  economic_proxy?: number | null;
  baseline_value?: number | null;
  edge?: number | null;
  scored_at?: string | null;
  detail: Record<string, unknown>;
}

export interface DecisionTraceResponse {
  signal: DecisionTraceSignal;
  summary: DecisionTraceSummary;
  llm_context: DecisionTraceLlmContext;
  strategy_inputs: DecisionTraceStrategyInputs;
  risk_orderability: DecisionTraceRiskOrderability;
  lineage: DecisionTraceLineage;
  lifecycle: DecisionTraceLifecycle;
  scorecard: DecisionTraceScorecard;
  evidence_gaps: DecisionTraceEvidenceGap[];
}

export const decisionTraceApi = {
  getDecisionTrace: (signalId: string, params?: { asset_class?: string }) =>
    apiClient.get<DecisionTraceResponse>(
      `/api/signals/${encodeURIComponent(signalId)}/trace`,
      { params },
    ),
};
