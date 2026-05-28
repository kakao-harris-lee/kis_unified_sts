// Shared types ported from the Vite SPA (dashboard-frontend/src/pages/*.tsx).
// Components in @/components/dashboard import from here instead of the page
// modules, so circular imports between layout components and page-default
// exports go away under the Next.js App Router.

export interface Position {
  asset_class?: 'stock' | 'futures';
  code: string;
  name: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_pct: number;
  strategy: string;
  entry_time: string;
}
