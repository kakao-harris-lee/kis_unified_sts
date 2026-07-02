import { apiClient } from "./client";

// Market Risk Score API (Phase 1c) — read-only transparency surface for the
// /market page and the Cockpit header chip. Mirrors
// services/dashboard/routes/market_risk.py response shapes.

export interface MarketRiskComponent {
  sub: number | null;
  weight: number | null;
  contribution: number | null;
  raw: unknown;
  asof: string | null;
}

export interface MarketRiskSnapshot {
  score: number | null;
  score_ema3: number | null;
  band: string | null;
  regime: string | null;
  degraded: boolean;
  coverage_ratio: number | null;
  missing_components: string[];
  kind: string | null;
  asof: string | null;
  age_s: number | null;
  stale: boolean;
  score_delta_1d: number | null;
  prev_close_score: number | null;
  prev_close_date: string | null;
  components: Record<string, MarketRiskComponent>;
}

export interface MarketStructureFreshness {
  status: string;
  source?: string;
  snapshot: string | null;
  trade_date: string | null;
  asof: string | null;
  age_s: number | null;
  coverage_ratio: number | null;
  missing_components: string[];
}

export interface NightCloseSummary {
  available: boolean;
  status: string;
  source?: string;
  close?: number | null;
  mrkt_basis?: number | null;
  dprt?: number | null;
  open_interest?: number | null;
  acml_vol?: number | null;
  product_code?: string | null;
  asof?: string | null;
  age_s?: number | null;
}

export interface MarketRiskLatest {
  status: "ok" | "degraded" | "stale" | "unavailable";
  checked_at: string;
  source: string;
  risk: MarketRiskSnapshot | null;
  structure: MarketStructureFreshness;
  night_close: NightCloseSummary;
}

export interface MarketRiskHistoryPoint {
  trade_date: string | null;
  risk_score: number | null;
  risk_score_ema3: number | null;
  coverage_ratio: number | null;
  kospi_close: number | null;
  kospi_change_pct: number | null;
  kospi_ret_20d: number | null;
  fut_close: number | null;
  fut_foreign_net_qty: number | null;
  fut_foreign_net_qty_cum20: number | null;
  basis: number | null;
  basis_dev: number | null;
  basis_dev_ma5: number | null;
  fut_oi: number | null;
  fut_oi_change: number | null;
  prog_net_val: number | null;
  usdkrw: number | null;
  usdkrw_ret_5d: number | null;
  es_ovn_ret: number | null;
  nq_ovn_ret: number | null;
  sox_ret: number | null;
  sub_foreign_fut: number | null;
  sub_basis: number | null;
  sub_usdkrw: number | null;
  sub_program: number | null;
  sub_oi: number | null;
  sub_overseas: number | null;
  sub_vol: number | null;
  sub_trend: number | null;
  risk_band: string | null;
  unified_regime: string | null;
  oi_price_signal: string | null;
  ma_alignment: string | null;
  degraded: boolean | null;
}

export interface MarketRiskHistory {
  status: "ok" | "empty";
  days: number;
  start: string;
  end: string;
  count: number;
  points: MarketRiskHistoryPoint[];
}

export const marketRiskApi = {
  getLatest: () => apiClient.get<MarketRiskLatest>("/api/market-risk"),
  getHistory: (params?: { days?: number }) =>
    apiClient.get<MarketRiskHistory>("/api/market-risk/history", { params }),
};

// ---------------------------------------------------------------------------
// Band metadata (roadmap §4.2) — shared by the /market gauge, the track
// response panel, and the Cockpit header chip.
// ---------------------------------------------------------------------------

export type RiskBand = "LOW" | "NEUTRAL" | "ELEVATED" | "HIGH" | "CRITICAL";

export interface RiskBandSpec {
  band: RiskBand;
  min: number;
  max: number;
  label: string;
}

export const RISK_BANDS: readonly RiskBandSpec[] = [
  { band: "LOW", min: 0, max: 29, label: "LOW (0–29)" },
  { band: "NEUTRAL", min: 30, max: 54, label: "NEUTRAL (30–54)" },
  { band: "ELEVATED", min: 55, max: 69, label: "ELEVATED (55–69)" },
  { band: "HIGH", min: 70, max: 84, label: "HIGH (70–84)" },
  { band: "CRITICAL", min: 85, max: 100, label: "CRITICAL (85–100)" },
] as const;

export function normalizeBand(band: string | null | undefined): RiskBand | null {
  const upper = (band ?? "").trim().toUpperCase();
  return (RISK_BANDS.find((spec) => spec.band === upper)?.band ?? null) as
    | RiskBand
    | null;
}
