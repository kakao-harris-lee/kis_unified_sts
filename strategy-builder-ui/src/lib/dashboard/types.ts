// Shared types ported from the Vite SPA (dashboard-frontend/src/pages/*.tsx).
// Components in @/components/dashboard import from here instead of the page
// modules, so circular imports between layout components and page-default
// exports go away under the Next.js App Router.

export interface Position {
  asset_class?: 'stock' | 'futures';
  code: string;
  name: string;
  side: 'BUY' | 'SELL' | 'long' | 'short';
  quantity: number;
  entry_price: number;
  current_price: number;
  market_value_krw?: number | null;
  unrealized_pnl: number;
  pnl_pct: number;
  strategy: string;
  entry_time: string;
}

export interface RiskPortfolio {
  equity_krw: number | null;
  cash_krw: number | null;
  gross_exposure_krw: number;
  net_exposure_krw: number;
  unrealized_pnl_krw: number;
  realized_pnl_krw: number | null;
  daily_pnl_krw: number;
  daily_loss_krw: number;
  open_positions: number;
  exposure_to_equity_pct: number | null;
  last_update: string;
}

export interface RiskStrategyExposure {
  asset_class: 'stock' | 'futures';
  strategy: string;
  positions: number;
  gross_exposure_krw: number;
  net_exposure_krw: number;
  unrealized_pnl_krw: number;
  exposure_to_equity_pct: number | null;
}

export interface RiskSymbolExposure {
  asset_class: 'stock' | 'futures';
  code: string;
  name: string;
  side: string;
  quantity: number;
  current_price: number;
  market_value_krw: number;
  signed_exposure_krw: number;
  unrealized_pnl_krw: number;
  pnl_pct: number;
  strategy: string;
}

export interface RiskExposure {
  asset_class: 'stock' | 'futures' | 'all';
  generated_at: string;
  portfolio: RiskPortfolio;
  by_strategy: RiskStrategyExposure[];
  by_symbol: RiskSymbolExposure[];
  notes: string[];
}
