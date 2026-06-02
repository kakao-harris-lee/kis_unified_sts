import { apiClient } from './client';

// Strategy Builder API
export const strategyBuilderApi = {
  getCapabilities: () => apiClient.get('/api/strategy-builder/capabilities'),
  validate: (state: unknown) => apiClient.post('/api/strategy-builder/validate', state),
  previewYaml: (state: unknown) => apiClient.post('/api/strategy-builder/preview-yaml', state),
  previewCode: (state: unknown) => apiClient.post('/api/strategy-builder/preview-code', state),
  importYaml: (yaml: string) => apiClient.post('/api/strategy-builder/import-yaml', { yaml }),
  previewSignals: (payload: unknown) =>
    apiClient.post('/api/strategy-builder/signals/preview', payload),
  createOrderTicket: (
    signalId: string,
    payload?: { quantity?: number; order_amount?: number },
  ) => apiClient.post(`/api/strategy-builder/signals/${signalId}/order-ticket`, payload || {}),
  submitPaperOrder: (ticketId: string) =>
    apiClient.post('/api/strategy-builder/orders/paper', { ticket_id: ticketId }),
};
