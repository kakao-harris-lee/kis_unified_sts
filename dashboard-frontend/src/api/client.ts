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
  getStatus: (params?: { asset_class?: string }) =>
    apiClient.get('/api/trading/status', { params }),
  getPositions: (params?: { asset_class?: string }) =>
    apiClient.get('/api/trading/positions', { params }),
  startTrading: (params?: { asset_class?: string }) =>
    apiClient.post('/api/trading/start', null, { params }),
  stopTrading: (params?: { asset_class?: string }) =>
    apiClient.post('/api/trading/stop', null, { params }),
};

// Signals API
export const signalsApi = {
  getSignals: (params?: { asset_class?: string; strategy?: string; side?: string; limit?: number }) =>
    apiClient.get('/api/signals', { params }),
  getHistory: (params?: { asset_class?: string; days?: number }) =>
    apiClient.get('/api/signals/history', { params }),
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

// Strategies API
export const strategiesApi = {
  list: (params?: { asset_class?: string; enabled_only?: boolean }) =>
    apiClient.get('/api/strategies', { params }),
};


// Fills API (Phase 2)
export const fillsApi = {
  getRecent: (params?: { asset_class?: string; limit?: number }) =>
    apiClient.get('/api/trades/fills', { params }),
}

// Health API (Phase 1 backend)
export const healthApi = {
  getSummary: (params?: { asset_class?: string }) =>
    apiClient.get('/api/health/summary', { params }),
  getProcess: () => apiClient.get('/api/health/process'),
  getDataFreshness: (params?: { asset_class?: string }) =>
    apiClient.get('/api/health/data-freshness', { params }),
  getKillSwitch: () => apiClient.get('/api/health/kill-switch'),
}

// Kill Switch API (Phase 2)
export const killSwitchApi = {
  trigger: () => apiClient.post('/api/trading/kill-switch'),
}
