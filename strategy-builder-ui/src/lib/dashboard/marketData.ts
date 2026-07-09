import { apiClient } from "./client";

// Historical OHLCV bars for the price-chart-with-markers view (read-only).
// Backed by services/dashboard/routes/market_data.py → ParquetMarketDataStore.

export interface OhlcvBar {
  t: string; // ISO timestamp
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface MarketBars {
  status: "ok" | "empty";
  symbol: string;
  asset_class: string;
  timeframe: "minute" | "daily";
  count: number;
  bars: OhlcvBar[];
}

export const marketDataApi = {
  getBars: (params: {
    symbol: string;
    asset_class?: string;
    timeframe?: "minute" | "daily";
    days?: number;
  }) => apiClient.get<MarketBars>("/api/market-data/bars", { params }),
};
