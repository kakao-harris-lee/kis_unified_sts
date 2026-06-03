import { apiClient } from './client';

// Trades API
export const tradesApi = {
  getTrades: (params?: { strategy?: string; side?: string; limit?: number }) =>
    apiClient.get('/api/trades', { params }),
  getStatistics: () => apiClient.get('/api/trades/statistics'),
  getByStrategy: () => apiClient.get('/api/trades/by-strategy'),
  getClosedStatistics: (params?: { asset_class?: string; strategy?: string }) =>
    apiClient.get('/api/trades/closed/statistics', { params }),
  getClosedTrades: (params?: { asset_class?: string; strategy?: string; limit?: number }) =>
    apiClient.get('/api/trades/closed', { params }),
};
