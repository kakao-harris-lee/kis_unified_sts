import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '';

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add API key header if configured
const apiKey = import.meta.env.VITE_API_KEY;
if (apiKey) {
  apiClient.defaults.headers.common['X-API-Key'] = apiKey;
}

// Trading API
export const tradingApi = {
  getStatus: () => apiClient.get('/api/trading/status'),
  getPositions: () => apiClient.get('/api/trading/positions'),
  startTrading: () => apiClient.post('/api/trading/start'),
  stopTrading: () => apiClient.post('/api/trading/stop'),
};

// Signals API
export const signalsApi = {
  getSignals: (params?: { strategy?: string; side?: string; limit?: number }) =>
    apiClient.get('/api/signals', { params }),
  getHistory: (days?: number) =>
    apiClient.get('/api/signals/history', { params: { days } }),
};

// Trades API
export const tradesApi = {
  getTrades: (params?: { strategy?: string; side?: string; limit?: number }) =>
    apiClient.get('/api/trades', { params }),
  getStatistics: () => apiClient.get('/api/trades/statistics'),
  getByStrategy: () => apiClient.get('/api/trades/by-strategy'),
  // ClickHouse RL endpoints
  getRlStatistics: (params?: { asset_class?: string; strategy?: string }) =>
    apiClient.get('/api/trades/rl/statistics', { params }),
  getRlTrades: (params?: { asset_class?: string; strategy?: string; limit?: number }) =>
    apiClient.get('/api/trades/rl', { params }),
};

// Backtest API
export const backtestApi = {
  list: () => apiClient.get('/api/backtest'),
  run: (params: {
    asset_class: string;
    strategy: string;
    symbol: string;
    start_date: string;
    end_date: string;
    initial_capital: number;
    params?: Record<string, unknown>;
  }) => apiClient.post('/api/backtest/run', params),
  getResult: (runId: string) => apiClient.get(`/api/backtest/${runId}`),
};

// Experiments API
export const experimentsApi = {
  list: () => apiClient.get('/api/experiments'),
  getRuns: (experimentId: string, params?: { status?: string; limit?: number }) =>
    apiClient.get(`/api/experiments/${experimentId}/runs`, { params }),
  getBest: (experimentId: string, metric?: string) =>
    apiClient.get(`/api/experiments/${experimentId}/best`, { params: { metric } }),
};

// Strategies API
export const strategiesApi = {
  list: (params?: { asset_class?: string; enabled_only?: boolean }) =>
    apiClient.get('/api/strategies', { params }),
  get: (asset: string, name: string) =>
    apiClient.get(`/api/strategies/${asset}/${name}`),
  save: (data: {
    asset_class: string;
    name: string;
    config: Record<string, unknown>;
  }) => apiClient.post('/api/strategies', data),
  validate: (data: {
    asset_class: string;
    config: Record<string, unknown>;
  }) => apiClient.post('/api/strategies/validate', data),
  schema: (params: { entry_type?: string; exit_type?: string; position_type?: string }) =>
    apiClient.get('/api/strategies/schema', { params }),
};
