import { apiGet } from "./client";

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
