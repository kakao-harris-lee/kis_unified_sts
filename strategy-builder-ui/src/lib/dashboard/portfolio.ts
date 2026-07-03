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

// ---------------------------------------------------------------------------
// Hedge advisor (Phase 4B — roadmap §5.4/§6.1). 권고 전용 — 자동 주문 없음:
// this client exposes no order or execution endpoints. Mirrors the
// portfolio:hedge:latest contract (mini KOSPI200 — O4). Notional/exposure
// fields are KRW.
// ---------------------------------------------------------------------------

export interface PortfolioHedgeSnapshot {
  product: string | null;
  /** KRW per index point (mini KOSPI200 = 50,000). */
  multiplier: number | null;
  futures_price: number | null;
  stock_long_notional: number | null;
  portfolio_beta: number | null;
  beta_notional: number | null;
  futures_net_contracts: number | null;
  /** Signed KRW notional — net short is negative. */
  futures_net_notional: number | null;
  net_beta_exposure: number | null;
  recommended_short_contracts: number | null;
  residual_exposure_after: number | null;
  band: string | null;
  score: number | null;
  advisory_active: boolean;
  reason: string | null;
  degraded: boolean;
  missing_components: string[];
  asof: string | null;
  age_s: number | null;
  stale: boolean;
}

export interface PortfolioHedgeLatest {
  status: "ok" | "degraded" | "stale" | "unavailable";
  checked_at: string;
  source: string;
  /** Fixed true marker — the advisor never places orders. */
  advisory_only: boolean;
  hedge: PortfolioHedgeSnapshot | null;
}

export interface PortfolioHedgeHistoryPoint {
  asof: string | null;
  trade_date: string | null;
  recommended_short_contracts: number | null;
  net_beta_exposure: number | null;
  beta_notional: number | null;
  futures_net_notional: number | null;
  residual_exposure_after: number | null;
  futures_price: number | null;
  score: number | null;
  product: string | null;
  band: string | null;
  reason: string | null;
  advisory_active: boolean | null;
}

export interface PortfolioHedgeHistory {
  status: "ok" | "empty";
  days: number;
  start: string;
  end: string;
  count: number;
  points: PortfolioHedgeHistoryPoint[];
}

// ---------------------------------------------------------------------------
// Track A core (Phase 5E — roadmap §5.3/§6.1). 수동 트랙 — 자동 매매 없음:
// this client exposes no trade or ledger-mutation endpoints. Mirrors the
// portfolio:tier3:watch contract plus the core_holdings.yaml loader (Phase 5A
// lane); either side may be null/empty while its lane has not landed.
// ---------------------------------------------------------------------------

export interface Tier3WatchSnapshot {
  kospi_close: number | null;
  kospi_peak: number | null;
  /** Drawdown from the KOSPI peak as a FRACTION (≤ 0; -0.16 = -16%) — same
   *  unit convention as monthly_mdd_pct above. Multiply by 100 for display. */
  drawdown: number | null;
  /** Trigger threshold as a FRACTION (-0.15 = -15%). */
  trigger_threshold: number | null;
  /** Watch lane's verdict — the UI never re-derives it. */
  triggered: boolean;
  asof: string | null;
  age_s: number | null;
  stale: boolean;
}

export interface CoreHoldingValuation {
  date: string | null;
  price: number | null;
}

export interface CoreHolding {
  symbol: string | null;
  name: string | null;
  sector: string | null;
  sector_label: string | null;
  thesis: string | null;
  kill_criteria: string[];
  shares: number | null;
  avg_price: number | null;
  last_valuation: CoreHoldingValuation | null;
  /** KRW — shares × (last valuation price ∥ 평단). */
  valuation: number | null;
  /** Fraction of the holdings total valuation. */
  weight: number | null;
}

export interface CoreCandidate {
  symbol: string | null;
  name: string | null;
  sector: string | null;
  sector_label: string | null;
  thesis: string | null;
  kill_criteria: string[];
}

export interface CoreSectorSpec {
  label: string;
  /** Target allocation as a fraction (0.35 = 35%). */
  target_weight: number | null;
  /** Actual allocation as a fraction; null while 미산출. */
  actual_weight: number | null;
}

export interface CoreRebalancing {
  /** Allocation drift threshold as a fraction (0.10 = ±10%p). */
  drift_threshold_pct: number | null;
  /** Single-holding weight cap as a fraction (0.25 = 25%). */
  single_holding_max: number | null;
}

export interface PortfolioCoreLatest {
  /** Reflects the Tier 3 watch publication; holdings degrade independently. */
  status: "ok" | "stale" | "unavailable";
  checked_at: string;
  source: string;
  /** Fixed true marker — Track A is manual, no automated trading. */
  manual_track: boolean;
  tier3: Tier3WatchSnapshot | null;
  holdings: CoreHolding[];
  candidates: CoreCandidate[];
  /** Null when the Phase 5A loader has not landed / failed to load. */
  sectors: Record<string, CoreSectorSpec> | null;
  rebalancing: CoreRebalancing | null;
}

const HEDGE_PRODUCT_LABELS: Record<string, string> = {
  mini_kospi200: "미니 KOSPI200",
};

export function hedgeProductLabel(
  product: string | null | undefined,
): string {
  const key = (product ?? "").trim().toLowerCase();
  if (!key) return "-";
  return HEDGE_PRODUCT_LABELS[key] ?? product ?? "-";
}

export const portfolioApi = {
  getEquity: () => apiClient.get<PortfolioEquityLatest>("/api/portfolio/equity"),
  getEquityHistory: (params?: { days?: number }) =>
    apiClient.get<PortfolioEquityHistory>("/api/portfolio/equity/history", {
      params,
    }),
  getHedge: () => apiClient.get<PortfolioHedgeLatest>("/api/portfolio/hedge"),
  getHedgeHistory: (params?: { days?: number }) =>
    apiClient.get<PortfolioHedgeHistory>("/api/portfolio/hedge/history", {
      params,
    }),
  getCore: () => apiClient.get<PortfolioCoreLatest>("/api/portfolio/core"),
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
