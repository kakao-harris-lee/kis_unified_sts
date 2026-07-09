import { apiClient } from "./client";

// Portfolio analytics (read-only) — strategy correlation + exposure history.

export interface StrategyCorrelation {
  status: "ok" | "empty" | "insufficient_data";
  strategies: string[];
  // Row-major matrix aligned to `strategies`; null when correlation undefined.
  matrix: (number | null)[][];
  days: number;
}

export interface ExposurePoint {
  trade_date: string;
  // one numeric key per symbol (gross exposure KRW); shape is dynamic.
  [symbol: string]: string | number;
}

export interface ExposureHistory {
  status: "ok" | "empty";
  symbols: string[];
  points: ExposurePoint[];
  days: number;
}

export const analyticsApi = {
  getStrategyCorrelation: (params?: { asset_class?: string; days?: number }) =>
    apiClient.get<StrategyCorrelation>("/api/analytics/strategy-correlation", {
      params,
    }),
  getExposureHistory: (params?: { asset_class?: string; days?: number }) =>
    apiClient.get<ExposureHistory>("/api/analytics/exposure-history", {
      params,
    }),
};
