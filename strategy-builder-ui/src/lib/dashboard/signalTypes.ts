export interface SignalTraceDetails {
  [key: string]: unknown;
}

export interface DashboardSignal {
  id: string;
  asset_class?: string;
  strategy: string;
  symbol: string;
  side: string;
  signal_type?: string;
  confidence?: number;
  strength?: number;
  price: number;
  timestamp: string;
  executed: boolean;
  setup_type?: string | null;
  status?: string | null;
  reason?: string | null;
  reject_stage?: string | null;
  reject_reason?: string | null;
  orderability_state?: string | null;
  orderability_details?: SignalTraceDetails | null;
  order_id?: string | null;
  fill_id?: string | null;
  position_id?: string | null;
  trade_id?: string | null;
}

export interface DashboardSignalsResponse {
  signals: DashboardSignal[];
  total: number;
  page?: number;
  limit?: number;
}
