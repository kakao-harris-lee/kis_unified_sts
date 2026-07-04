import { apiClient } from './client';
import type { IndicatorCategory } from '@/types/builder';

// ── Capabilities response contract ─────────────────────────────────────────
// Mirrors backend `shared/strategy_builder/schema.py`:
//   BuilderCapabilities.indicators[] = IndicatorDefinition (snake_case;
//   `model_config = extra="forbid"` — NO camelCase alias_generator).
// We still tolerate camelCase aliases defensively; the mapper in
// `lib/builder/indicatorCatalog.ts` reads snake_case first, camel as fallback.

export interface CapabilityIndicatorParam {
  name: string;
  type?: 'number' | 'string';
  default: number | string;
  min?: number;
  max?: number;
  step?: number;
  description?: string;
}

export interface CapabilityIndicatorOutput {
  id: string;
  name: string;
  description?: string;
}

export interface CapabilityIndicator {
  id: string;
  name: string;
  name_ko?: string;
  nameKo?: string;
  category: IndicatorCategory;
  description?: string;
  params?: CapabilityIndicatorParam[];
  outputs?: CapabilityIndicatorOutput[];
  default_output?: string;
  defaultOutput?: string;
  implemented?: boolean;
  backtest_supported?: boolean;
  backtestSupported?: boolean;
  runtime_supported?: boolean;
  runtimeSupported?: boolean;
}

export interface BuilderCapabilitiesResponse {
  indicators: CapabilityIndicator[];
  operators?: string[];
  price_fields?: string[];
  risk_fields?: Record<string, unknown>;
  default_order_amount?: number;
  ttl_seconds?: number;
}

export interface PromotionRegisteredStrategy {
  id: string;
  name: string;
  description?: string | null;
  asset_class: string;
  enabled: boolean;
  registered_at?: string | null;
  path: string;
}

export interface PromotionRegisteredListResponse {
  strategies: PromotionRegisteredStrategy[];
  total: number;
}

export interface PromotionActivity {
  id: string;
  signals: number;
  trades: number;
}

export interface PromotionActivityResponse {
  activity: PromotionActivity[];
}

export interface PromotionExperimentSummary {
  strategy_id: string;
  strategy_name?: string | null;
  total_return_pct?: number | null;
  closed_trades?: number | null;
  win_rate_pct?: number | null;
  max_drawdown_pct?: number | null;
  sharpe_ratio?: number | null;
}

export interface PromotionExperimentReport {
  experiment?: {
    id?: string | null;
    generated_at?: string | null;
  };
  summaries?: PromotionExperimentSummary[];
  status_by_strategy?: Array<{
    strategy_id: string;
    status: 'ok' | 'skipped' | 'error';
    error?: string | null;
  }>;
}

export interface PromotionLatestExperimentResponse {
  report: PromotionExperimentReport | null;
}

export interface PromotionPaperComparisonRow {
  strategy_id: string;
  strategy_name?: string | null;
  status: 'aligned' | 'watch' | 'fail' | 'insufficient_data';
  missing_evidence: string[];
  backtest: {
    closed_trades: number;
    win_rate_pct: number | null;
    total_return_pct: number | null;
    max_drawdown_pct: number | null;
    sharpe_ratio: number | null;
  };
  paper: {
    trade_count: number;
    win_rate_pct: number | null;
    total_pnl: number;
    latest_exit_time: string | null;
  };
}

export interface PromotionPaperComparison {
  generated_at: string;
  source: {
    experiment_id: string | null;
    experiment_generated_at: string | null;
    ledger_available: boolean;
    min_paper_trades: number;
  };
  comparisons: PromotionPaperComparisonRow[];
  missing_evidence: string[];
}

export interface StrategyPromotionSources {
  registered: PromotionRegisteredStrategy[];
  activity: PromotionActivity[];
  latestReport: PromotionExperimentReport | null;
  paperComparison: PromotionPaperComparison | null;
  sourceErrors: string[];
}

async function unwrap<T>(request: Promise<{ data: T }>): Promise<T> {
  return (await request).data;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// Strategy Builder API
export const strategyBuilderApi = {
  getCapabilities: () =>
    apiClient.get<BuilderCapabilitiesResponse>('/api/strategy-builder/capabilities'),
  validate: (state: unknown) => apiClient.post('/api/strategy-builder/validate', state),
  previewYaml: (state: unknown) => apiClient.post('/api/strategy-builder/preview-yaml', state),
  previewCode: (state: unknown) => apiClient.post('/api/strategy-builder/preview-code', state),
  importYaml: (yaml: string) => apiClient.post('/api/strategy-builder/import-yaml', { yaml }),
  previewSignals: (payload: unknown) =>
    apiClient.post('/api/strategy-builder/signals/preview', payload),
  createOrderTicket: (
    signalId: string,
    payload?: { quantity?: number; order_amount?: number },
  ) => apiClient.post(`/api/strategy-builder/signals/${signalId}/order-ticket`, payload || {}),
  submitPaperOrder: (ticketId: string) =>
    apiClient.post('/api/strategy-builder/orders/paper', { ticket_id: ticketId }),
};

export async function getPromotionRegisteredStrategies(): Promise<PromotionRegisteredListResponse> {
  return unwrap(apiClient.get<PromotionRegisteredListResponse>('/api/kis-builder/registered'));
}

export async function getPromotionActivity(): Promise<PromotionActivityResponse> {
  return unwrap(apiClient.get<PromotionActivityResponse>('/api/kis-builder/registered/activity'));
}

export async function getPromotionLatestExperiment(): Promise<PromotionLatestExperimentResponse> {
  return unwrap(apiClient.get<PromotionLatestExperimentResponse>('/api/experiments/latest'));
}

export async function getPromotionPaperComparison(): Promise<PromotionPaperComparison> {
  return unwrap(apiClient.get<PromotionPaperComparison>('/api/experiments/latest/compare-paper'));
}

export async function getStrategyPromotionSources(): Promise<StrategyPromotionSources> {
  const [registered, activity, latestReport, paperComparison] = await Promise.allSettled([
    getPromotionRegisteredStrategies(),
    getPromotionActivity(),
    getPromotionLatestExperiment(),
    getPromotionPaperComparison(),
  ]);

  const sourceErrors: string[] = [];
  if (registered.status === 'rejected') {
    sourceErrors.push(`registered: ${errorMessage(registered.reason)}`);
  }
  if (activity.status === 'rejected') {
    sourceErrors.push(`activity: ${errorMessage(activity.reason)}`);
  }
  if (latestReport.status === 'rejected') {
    sourceErrors.push(`latest_experiment: ${errorMessage(latestReport.reason)}`);
  }
  if (paperComparison.status === 'rejected') {
    sourceErrors.push(`paper_comparison: ${errorMessage(paperComparison.reason)}`);
  }

  return {
    registered: registered.status === 'fulfilled' ? registered.value.strategies : [],
    activity: activity.status === 'fulfilled' ? activity.value.activity : [],
    latestReport: latestReport.status === 'fulfilled' ? latestReport.value.report : null,
    paperComparison: paperComparison.status === 'fulfilled' ? paperComparison.value : null,
    sourceErrors,
  };
}
