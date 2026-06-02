import { apiClient } from './client';

// Signals API
export const signalsApi = {
  getSignals: (params?: { asset_class?: string; strategy?: string; side?: string; limit?: number }) =>
    apiClient.get('/api/signals', { params }),
  getHistory: (params?: { asset_class?: string; days?: number }) =>
    apiClient.get('/api/signals/history', { params }),
};
