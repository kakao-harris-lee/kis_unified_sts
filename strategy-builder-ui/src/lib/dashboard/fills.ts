import { apiClient } from './client';

// Fills API (Phase 2)
export const fillsApi = {
  getRecent: (params?: { asset_class?: string; limit?: number }) =>
    apiClient.get('/api/trades/fills', { params }),
};
