import { apiClient } from './client';

// Health API (Phase 1 backend)
export const healthApi = {
  getSummary: (params?: { asset_class?: string }) =>
    apiClient.get('/api/health/summary', { params }),
  getProcess: () => apiClient.get('/api/health/process'),
  getDataFreshness: (params?: { asset_class?: string }) =>
    apiClient.get('/api/health/data-freshness', { params }),
  getKillSwitch: () => apiClient.get('/api/health/kill-switch'),
};
