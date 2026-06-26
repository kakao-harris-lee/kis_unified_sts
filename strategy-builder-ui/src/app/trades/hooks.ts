"use client";

import { useQuery } from '@tanstack/react-query';
import { useAssetClass } from '@/contexts/dashboard/AssetClassContext';
import { tradingApi, tradesApi } from '@/lib/dashboard/api';
import { QUERY_INTERVALS_MS } from '@/lib/dashboard/queryIntervals';
import type { TradeLifecycleResponse } from '@/lib/dashboard/trades';

export interface Trade {
  id: string;
  strategy: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  entry_time: string;
  exit_time: string;
}

export interface TradesResponse {
  trades: Trade[];
  total: number;
}

export interface StrategyStats {
  strategy: string;
  trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
}

export interface DbTrade {
  id: string;
  code: string;
  name: string;
  strategy: string;
  side: string;
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  quantity: number;
  pnl: number;
  exit_reason: string;
}

export interface DbStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  max_win: number;
  max_loss: number;
}

export interface DbOpenPosition {
  id: string;
  code: string;
  name: string;
  strategy: string;
  side: string;
  entry_date: string;
  entry_price: number;
  quantity: number;
  current_state: string;
  high_since_entry: number;
  stop_loss_price: number;
}

export function pnlTone(value: number | null | undefined): string {
  return (value ?? 0) >= 0 ? 'text-emerald-700' : 'text-rose-700';
}

export function buildCumulativePnlData(trades: Trade[] | undefined) {
  return (
    trades
      ?.slice()
      .reverse()
      .reduce(
        (acc, trade, idx) => {
          const cumPnl = (acc[idx - 1]?.cumPnl || 0) + trade.pnl_pct;
          acc.push({
            idx: idx + 1,
            pnl: trade.pnl_pct,
            cumPnl,
            date: new Date(trade.exit_time).toLocaleDateString(),
          });
          return acc;
        },
        [] as { idx: number; pnl: number; cumPnl: number; date: string }[]
      ) || []
  );
}

export function useLiveTradesQueries(
  strategyFilter: string,
  selectedLifecycleTrade: Trade | null
) {
  const { selectedAsset } = useAssetClass();

  const tradesQuery = useQuery<TradesResponse>({
    queryKey: ['trades', selectedAsset, strategyFilter],
    queryFn: () =>
      tradesApi
        .getTrades({
          asset_class: selectedAsset,
          strategy: strategyFilter || undefined,
          limit: 100,
        })
        .then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.fast,
  });

  const lifecycleQuery = useQuery<TradeLifecycleResponse>({
    queryKey: [
      'trade-lifecycle',
      'live',
      selectedAsset,
      selectedLifecycleTrade?.id,
      selectedLifecycleTrade?.symbol,
    ],
    queryFn: () =>
      tradesApi
        .getLifecycle({
          asset_class: selectedAsset,
          trade_id: selectedLifecycleTrade?.id,
          symbol: selectedLifecycleTrade?.symbol,
        })
        .then((r) => r.data),
    enabled: Boolean(selectedLifecycleTrade),
  });

  const byStrategyQuery = useQuery<StrategyStats[]>({
    queryKey: ['trades-by-strategy', selectedAsset],
    queryFn: () => tradesApi.getByStrategy({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.fast,
  });

  return {
    selectedAsset,
    tradesQuery,
    lifecycleQuery,
    byStrategyQuery,
  };
}

export function useHistoryTradesQueries(selectedLifecycleTrade: DbTrade | null) {
  const { selectedAsset } = useAssetClass();

  const statsQuery = useQuery<DbStats>({
    queryKey: ['db-statistics', selectedAsset],
    queryFn: async () => {
      const r = await tradesApi.getClosedStatistics({ asset_class: selectedAsset });
      return r.data;
    },
    refetchInterval: QUERY_INTERVALS_MS.slow,
  });

  const tradesQuery = useQuery<DbTrade[]>({
    queryKey: ['db-trades', selectedAsset],
    queryFn: async () => {
      const r = await tradesApi.getClosedTrades({ asset_class: selectedAsset, limit: 100 });
      return Array.isArray(r.data) ? r.data : [];
    },
    refetchInterval: QUERY_INTERVALS_MS.slow,
  });

  const openPositionsQuery = useQuery<DbOpenPosition[]>({
    queryKey: ['db-open-positions', selectedAsset],
    queryFn: () =>
      tradingApi
        .getPositions({ asset_class: selectedAsset })
        .then((r) => (Array.isArray(r.data) ? r.data : [])),
    refetchInterval: QUERY_INTERVALS_MS.fast,
  });

  const lifecycleQuery = useQuery<TradeLifecycleResponse>({
    queryKey: [
      'trade-lifecycle',
      'history',
      selectedAsset,
      selectedLifecycleTrade?.id,
      selectedLifecycleTrade?.code,
    ],
    queryFn: () =>
      tradesApi
        .getLifecycle({
          asset_class: selectedAsset,
          trade_id: selectedLifecycleTrade?.id,
          symbol: selectedLifecycleTrade?.code,
        })
        .then((r) => r.data),
    enabled: Boolean(selectedLifecycleTrade),
  });

  return {
    selectedAsset,
    statsQuery,
    tradesQuery,
    openPositionsQuery,
    lifecycleQuery,
  };
}
