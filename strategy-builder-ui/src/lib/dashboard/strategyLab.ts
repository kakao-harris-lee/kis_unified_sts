import { apiClient } from './client';

// Strategy Lab API
export const strategyLabApi = {
  getCapabilities: () => apiClient.get('/api/strategy-lab/capabilities'),
  validate: (spec: unknown) => apiClient.post('/api/strategy-lab/validate', spec),
  previewCode: (spec: unknown) => apiClient.post('/api/strategy-lab/preview-code', spec),
  previewSignal: (payload: unknown) =>
    apiClient.post('/api/strategy-lab/preview-signal', payload),
  getSignal: (signalId: string) =>
    apiClient.get(`/api/strategy-lab/signals/${signalId}`),
  createOrderTicket: (
    signalId: string,
    payload?: { quantity?: number; order_amount?: number },
  ) => apiClient.post(`/api/strategy-lab/signals/${signalId}/order-ticket`, payload || {}),
  submitPaperOrder: (ticketId: string) =>
    apiClient.post('/api/strategy-lab/orders/paper', { ticket_id: ticketId }),
};
