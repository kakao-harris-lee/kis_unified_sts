import { apiClient } from './client';

// Trading API
export const tradingApi = {
  getStatus: (params?: { asset_class?: string }) =>
    apiClient.get('/api/trading/status', { params }),
  getPositions: (params?: { asset_class?: string }) =>
    apiClient.get('/api/trading/positions', { params }),
  getRiskExposure: (params?: { asset_class?: string }) =>
    apiClient.get('/api/trading/risk-exposure', { params }),
  startTrading: (params?: { asset_class?: string }) =>
    apiClient.post('/api/trading/start', null, { params }),
  stopTrading: (params?: { asset_class?: string }) =>
    apiClient.post('/api/trading/stop', null, { params }),
};
