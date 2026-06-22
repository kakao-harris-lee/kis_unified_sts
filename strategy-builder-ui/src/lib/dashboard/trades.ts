import { apiClient } from './client';

export interface TradeLifecycleStep {
  stage: string;
  label: string;
  status: string;
  id: string | null;
  timestamp: string | null;
  source: string;
  summary: string | null;
  details: Record<string, string | number | boolean | null>;
}

export interface TradeLifecycleResponse {
  asset_class: string;
  as_of: string;
  filters: Record<string, string>;
  lineage: {
    signal_id: string | null;
    order_id: string | null;
    fill_id: string | null;
    trade_id: string | null;
    position_id: string | null;
  };
  steps: TradeLifecycleStep[];
  warnings: string[];
}

export interface TradeLifecycleParams {
  signal_id?: string;
  order_id?: string;
  fill_id?: string;
  trade_id?: string;
  symbol?: string;
  asset_class?: string;
}

// Trades API
export const tradesApi = {
  getTrades: (params?: { strategy?: string; side?: string; limit?: number; asset_class?: string }) =>
    apiClient.get('/api/trades', { params }),
  getStatistics: () => apiClient.get('/api/trades/statistics'),
  getByStrategy: (params?: { asset_class?: string }) =>
    apiClient.get('/api/trades/by-strategy', { params }),
  getClosedStatistics: (params?: { asset_class?: string; strategy?: string }) =>
    apiClient.get('/api/trades/closed/statistics', { params }),
  getClosedTrades: (params?: { asset_class?: string; strategy?: string; limit?: number }) =>
    apiClient.get('/api/trades/closed', { params }),
  getLifecycle: (params?: TradeLifecycleParams) =>
    apiClient.get<TradeLifecycleResponse>('/api/trades/lifecycle', { params }),
};
