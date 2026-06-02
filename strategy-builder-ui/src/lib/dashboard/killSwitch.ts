import { apiClient } from './client';

// Kill Switch API (Phase 2)
export const killSwitchApi = {
  trigger: () => apiClient.post('/api/trading/kill-switch'),
};
