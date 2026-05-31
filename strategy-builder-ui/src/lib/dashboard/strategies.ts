import { apiClient } from './client';

// Strategies API
export const strategiesApi = {
  list: (params?: { asset_class?: string; enabled_only?: boolean }) =>
    apiClient.get('/api/strategies', { params }),
};
