import { apiClient } from "./client";

// Unified portfolio equity API (Phase 3D) — read-only transparency surface
// for the /risk page. Mirrors services/dashboard/routes/portfolio.py
// response shapes. The circuit breaker is shadow-first (미집행); this client
// exposes no control endpoints.

export interface PortfolioEquitySnapshot {
  total_equity: number | null;
  track_a_equity: number | null;
  track_b_equity: number | null;
  track_c_equity: number | null;
  month_start_equity: number | null;
  month_peak_equity: number | null;
  /** Monthly drawdown as a FRACTION (≤ 0; -0.0494 = -4.94%) — same unit
   *  as the stages thresholds below. Multiply by 100 for display. */
  monthly_mdd_pct: number | null;
  stage: string | null;
  mode: string | null;
  degraded: boolean;
  missing_components: string[];
  asof: string | null;
  age_s: number | null;
  stale: boolean;
}

// MDD stage thresholds sourced from config/portfolio.yaml (fractions of
// month-start equity, e.g. -0.05 = -5%). Display-only.
export interface PortfolioMddStages {
  mode: string;
  reduce: { threshold: number; new_entry_size_factor: number };
  halt_new: { threshold: number };
  full_stop: { threshold: number };
}

export interface PortfolioEquityLatest {
  status: "ok" | "degraded" | "stale" | "unavailable";
  checked_at: string;
  source: string;
  equity: PortfolioEquitySnapshot | null;
  stages: PortfolioMddStages | null;
}

export interface PortfolioEquityHistoryPoint {
  trade_date: string | null;
  total_equity: number | null;
  track_a_equity: number | null;
  track_b_equity: number | null;
  track_c_equity: number | null;
  month_start_equity: number | null;
  month_peak_equity: number | null;
  monthly_mdd_pct: number | null;
  stage: string | null;
  mode: string | null;
}

export interface PortfolioEquityHistory {
  status: "ok" | "empty";
  days: number;
  start: string;
  end: string;
  count: number;
  points: PortfolioEquityHistoryPoint[];
}

export const portfolioApi = {
  getEquity: () => apiClient.get<PortfolioEquityLatest>("/api/portfolio/equity"),
  getEquityHistory: (params?: { days?: number }) =>
    apiClient.get<PortfolioEquityHistory>("/api/portfolio/equity/history", {
      params,
    }),
};

// ---------------------------------------------------------------------------
// Stage metadata (roadmap §5.5 / 설계서 §7.1) — shared by the /risk panel
// and charts. Stages only gate Track B/C NEW entries; Track A is never sold.
// ---------------------------------------------------------------------------

export type PortfolioStage = "NORMAL" | "REDUCE" | "HALT_NEW" | "FULL_STOP";

export interface PortfolioStageSpec {
  stage: PortfolioStage;
  label: string;
  description: string;
}

export const PORTFOLIO_STAGES: readonly PortfolioStageSpec[] = [
  { stage: "NORMAL", label: "NORMAL", description: "정상" },
  { stage: "REDUCE", label: "REDUCE", description: "신규 사이즈 50%" },
  { stage: "HALT_NEW", label: "HALT_NEW", description: "신규 진입 중단" },
  { stage: "FULL_STOP", label: "FULL_STOP", description: "전 시스템 정지" },
] as const;

export function normalizeStage(
  stage: string | null | undefined,
): PortfolioStage | null {
  const upper = (stage ?? "").trim().toUpperCase();
  return (PORTFOLIO_STAGES.find((spec) => spec.stage === upper)?.stage ??
    null) as PortfolioStage | null;
}
