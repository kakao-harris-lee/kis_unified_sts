import { apiGet, apiPost } from "./client";

// --- Phase 3/4: registry-strategy experiments (real BacktestEngine) ----------

export interface RunStrategySummary {
  strategy_id: string;
  strategy_name: string;
  engine: string;
  timeframe: string;
  initial_capital: number;
  final_equity: number | null;
  total_return_pct: number | null;
  realized_pnl: number | null;
  unrealized_pnl: number;
  closed_trades: number;
  admitted_entries: number;
  open_positions: number;
  win_rate_pct: number;
  max_drawdown_pct: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  profit_factor: number | null;
  symbols_ran?: number;
}

export interface StrategyStatus {
  strategy_id: string;
  status: "ok" | "skipped" | "error";
  error: string | null;
}

export interface ExperimentRunReport {
  experiment: {
    id: string;
    description: string;
    start_date: string;
    end_date: string;
    generated_at: string;
    symbols: string[];
    strategies: string[];
    initial_capital: number;
  };
  data_coverage: Record<
    string,
    { loaded: boolean; rows?: number; start?: string; end?: string; error?: string }
  >;
  summaries: RunStrategySummary[];
  equity_curves: Record<string, Array<{ date: string; equity: number }>>;
  trades: Array<Record<string, unknown>>;
  status_by_strategy: StrategyStatus[];
}

export type ExperimentPaperComparisonStatus =
  | "aligned"
  | "watch"
  | "fail"
  | "insufficient_data";

export interface ExperimentPaperComparisonRow {
  strategy_id: string;
  strategy_name?: string | null;
  status: ExperimentPaperComparisonStatus;
  missing_evidence: string[];
  backtest: {
    closed_trades: number;
    win_rate_pct: number | null;
    total_return_pct: number | null;
    realized_pnl: number | null;
    profit_factor: number | null;
    max_drawdown_pct: number | null;
    sharpe_ratio: number | null;
  };
  paper: {
    trade_count: number;
    winning_trades: number;
    losing_trades: number;
    win_rate_pct: number | null;
    total_pnl: number;
    avg_pnl: number | null;
    avg_pnl_pct: number | null;
    profit_factor: number | null;
    symbols: string[];
    latest_exit_time: string | null;
  };
  deltas: {
    trade_count: number;
    win_rate_pct: number | null;
    pnl_vs_realized: number | null;
  };
}

export interface ExperimentPaperComparison {
  generated_at: string;
  source: {
    experiment_id: string | null;
    experiment_generated_at: string | null;
    ledger_available: boolean;
    min_paper_trades: number;
  };
  comparisons: ExperimentPaperComparisonRow[];
  missing_evidence: string[];
}

export interface ExperimentJob {
  job_id: string;
  status: "queued" | "running" | "done" | "failed";
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  experiment_id?: string | null;
  report?: ExperimentRunReport | null;
}

export interface StrategyCatalogItem {
  name: string;
  enabled: boolean;
  timeframe: string;
  description: string;
}

export interface RunExperimentRequest {
  strategies?: Array<{ type: string; name: string; asset?: string }>;
  symbols?: string[];
  start?: string;
  end?: string;
  lookback_days?: number;
  id?: string;
  description?: string;
}

export async function getExperimentStrategies(): Promise<{
  strategies: StrategyCatalogItem[];
}> {
  return apiGet("/api/experiments/strategies");
}

export async function getLatestExperiment(): Promise<{
  report: ExperimentRunReport | null;
}> {
  return apiGet("/api/experiments/latest");
}

export async function getLatestExperimentPaperComparison(): Promise<ExperimentPaperComparison> {
  return apiGet<ExperimentPaperComparison>("/api/experiments/latest/compare-paper");
}

export interface DivergencePoint {
  trade_date: string;
  backtest_cum_pct: number;
  paper_cum_pct: number;
  divergence_pct: number;
}

export interface ExperimentDivergence {
  status: "ok" | "no_report" | "insufficient_data";
  as_of: string;
  points: DivergencePoint[];
  missing_evidence?: string[];
}

export async function getLatestExperimentDivergence(): Promise<ExperimentDivergence> {
  return apiGet<ExperimentDivergence>("/api/experiments/latest/divergence");
}

export async function runExperiment(
  body: RunExperimentRequest,
): Promise<ExperimentJob> {
  return apiPost<ExperimentJob>("/api/experiments/run", body);
}

export async function getExperimentJob(jobId: string): Promise<ExperimentJob> {
  return apiGet<ExperimentJob>(
    `/api/experiments/jobs/${encodeURIComponent(jobId)}`,
  );
}

export interface ExperimentSummary {
  strategy_id: string;
  strategy_name: string;
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  realized_pnl: number;
  unrealized_pnl: number;
  closed_trades: number;
  open_positions: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  entry_signals: number;
  admitted_entries: number;
  exit_signals: number;
  rejected_existing_position: number;
  rejected_max_positions: number;
  rejected_insufficient_cash: number;
}

export interface ExperimentReportInfo {
  filename: string;
  path: string;
  mtime: string;
  generated_at?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  summary_count: number;
  trade_count: number;
}

export interface ExperimentProgress {
  status: string;
  total_scheduled_days: number;
  completed_report_days: number;
  completion_pct: number;
  report_dates: string[];
  next_run_at_kst?: string | null;
  last_report_at?: string | null;
}

export interface ExperimentConfig {
  id: string;
  description: string;
  start_date: string;
  end_date: string;
  output_dir: string;
  daily_run_time_kst: string;
  presets: string[];
  fallback_symbols: string[];
  basket_source: Record<string, unknown>;
}

export interface ExperimentResult {
  experiment: {
    id: string;
    description: string;
    start_date: string;
    end_date: string;
    generated_at: string;
    symbols: string[];
    presets: string[];
    initial_capital: number;
    order_amount_per_stock: number;
    max_positions_per_strategy: number;
    min_signal_strength: number;
    costs: Record<string, number>;
  };
  summaries: ExperimentSummary[];
  trades: Array<Record<string, unknown>>;
  equity_curves: Record<string, Array<{ date: string; equity: number }>>;
  data_coverage: Record<string, Record<string, unknown>>;
}

export interface ExperimentStatusResponse {
  experiment: ExperimentConfig;
  progress: ExperimentProgress;
  reports: ExperimentReportInfo[];
  latest_report?: ExperimentResult | null;
  latest_log?: {
    path: string;
    mtime: string;
    lines: string[];
  } | null;
}

export async function getStockBuilderPresetExperiment(): Promise<ExperimentStatusResponse> {
  return apiGet<ExperimentStatusResponse>("/api/experiments/stock-builder-preset");
}
