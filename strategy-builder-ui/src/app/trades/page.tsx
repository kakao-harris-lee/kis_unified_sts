"use client";

import { useState, type KeyboardEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { Clock3, RefreshCcw } from 'lucide-react';
import { tradingApi, tradesApi } from '@/lib/dashboard/api';
import TableSkeleton from '@/components/dashboard/TableSkeleton';
import RefreshIndicator from '@/components/dashboard/RefreshIndicator';
import ErrorMessage from '@/components/dashboard/ErrorMessage';
import SideBadge from '@/components/dashboard/SideBadge';
import StatCard from '@/components/dashboard/StatCard';
import StrategySelect from '@/components/dashboard/StrategySelect';
import HeaderBar from '@/components/dashboard/HeaderBar';
import LifecycleTimeline from '@/components/dashboard/LifecycleTimeline';
import { useAssetClass } from '@/contexts/dashboard/AssetClassContext';
import { QUERY_INTERVALS_MS } from '@/lib/dashboard/queryIntervals';
import type { TradeLifecycleResponse } from '@/lib/dashboard/trades';

interface Trade {
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

interface TradesResponse {
  trades: Trade[];
  total: number;
}

interface StrategyStats {
  strategy: string;
  trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
}

interface DbTrade {
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

interface DbStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  max_win: number;
  max_loss: number;
}

interface DbOpenPosition {
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

type TabType = 'live' | 'history';

function LifecycleIconButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-900"
    >
      <Clock3 className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}

function LifecycleTextButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="mt-3 inline-flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900"
    >
      <Clock3 className="h-4 w-4" aria-hidden="true" />
      Lifecycle
    </button>
  );
}

function pnlTone(value: number | null | undefined): string {
  return (value ?? 0) >= 0 ? 'text-emerald-700' : 'text-rose-700';
}

function LiveTab() {
  const { selectedAsset } = useAssetClass();
  const [strategyFilter, setStrategyFilter] = useState<string>('');
  const [chartCollapsed, setChartCollapsed] = useState<boolean>(true);
  const [selectedLifecycleTrade, setSelectedLifecycleTrade] = useState<Trade | null>(null);
  const chartPanelId = 'live-trade-charts';

  const {
    data: tradesData,
    isLoading: tradesLoading,
    error: tradesError,
    refetch: refetchTrades,
    dataUpdatedAt: tradesUpdatedAt,
    isRefetching: tradesRefetching,
  } = useQuery<TradesResponse>({
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

  const {
    data: lifecycleData,
    isLoading: lifecycleLoading,
    error: lifecycleError,
    refetch: refetchLifecycle,
  } = useQuery<TradeLifecycleResponse>({
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

  const {
    data: byStrategy,
    error: strategyError,
    refetch: refetchStrategy,
  } = useQuery<StrategyStats[]>({
    queryKey: ['trades-by-strategy', selectedAsset],
    queryFn: () => tradesApi.getByStrategy({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.fast,
  });

  const cumulativePnlData =
    tradesData?.trades
      .slice()
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
      ) || [];

  // Error states
  if (tradesError) {
    return (
      <ErrorMessage
        message={tradesError instanceof Error ? tradesError.message : 'Failed to load trades'}
        onRetry={() => refetchTrades()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <StrategySelect
          value={strategyFilter}
          onChange={setStrategyFilter}
          assetClass={selectedAsset}
        />
        <div className="flex items-center gap-4">
          <RefreshIndicator
            lastUpdated={tradesUpdatedAt}
            isRefreshing={tradesRefetching}
            showStaleWarning={true}
            staleThresholdSeconds={30}
          />
          <button
            type="button"
            onClick={() => {
              refetchTrades();
              refetchStrategy();
            }}
            className="inline-flex h-9 w-9 items-center justify-center rounded border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-900"
            aria-label="Refresh live trades"
          >
            <RefreshCcw className="h-4 w-4" aria-hidden="true" />
          </button>
          <div className="text-sm text-slate-500">{tradesData?.total || 0} trade(s)</div>
        </div>
      </div>

      {/* Mobile chart toggle */}
      <div className="sm:hidden">
        <button
          type="button"
          onClick={() => setChartCollapsed((v) => !v)}
          aria-expanded={!chartCollapsed}
          aria-controls={chartPanelId}
          className="w-full px-4 py-2 bg-white border border-slate-300 rounded text-sm text-slate-800"
        >
          📊 {chartCollapsed ? '차트 보기' : '차트 숨기기'}
        </button>
      </div>

      <div
        id={chartPanelId}
        className={`${chartCollapsed ? 'hidden' : 'block'} sm:block grid grid-cols-1 lg:grid-cols-2 gap-6`}
      >
        <div className="bg-white rounded-lg p-4 border border-slate-200">
          <h3 className="text-lg font-medium mb-4">Cumulative P&L (%)</h3>
          {tradesLoading ? (
            <div className="h-[250px] flex items-center justify-center">
              <div className="animate-pulse text-slate-500">Loading chart...</div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={cumulativePnlData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="idx" stroke="#9CA3AF" fontSize={12} />
                <YAxis stroke="#9CA3AF" fontSize={12} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                />
                <Line type="monotone" dataKey="cumPnl" stroke="#10B981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="bg-white rounded-lg p-4 border border-slate-200">
          <h3 className="text-lg font-medium mb-4">Performance by Strategy</h3>
          {tradesLoading || strategyError ? (
            <div className="h-[250px] flex items-center justify-center">
              {strategyError ? (
                <div className="text-center">
                  <div className="text-rose-700 text-sm mb-2">Failed to load</div>
                  <button
                    onClick={() => refetchStrategy()}
                    className="text-xs text-blue-400 hover:text-blue-300"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <div className="animate-pulse text-slate-500">Loading chart...</div>
              )}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={byStrategy || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="strategy" stroke="#9CA3AF" fontSize={12} />
                <YAxis stroke="#9CA3AF" fontSize={12} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                />
                <Bar dataKey="total_pnl" fill="#3B82F6" name="Total P&L %" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {selectedLifecycleTrade ? (
        <LifecycleTimeline
          title={`Lifecycle ${selectedLifecycleTrade.symbol}`}
          data={lifecycleData}
          isLoading={lifecycleLoading}
          error={
            lifecycleError instanceof Error
              ? lifecycleError.message
              : lifecycleError
                ? 'Failed to load lifecycle'
                : null
          }
          onRetry={() => refetchLifecycle()}
          onClose={() => setSelectedLifecycleTrade(null)}
        />
      ) : null}

      {tradesLoading ? (
        <>
          <div role="status" aria-label="Loading live trades" className="sr-only">
            Loading live trades
          </div>
          <TableSkeleton rows={10} columns={9} />
        </>
      ) : tradesData?.trades.length === 0 ? (
        <div className="bg-white rounded-lg p-8 text-center text-slate-500">No trades found</div>
      ) : (
        <>
          {/* Mobile Card View */}
          <div className="block md:hidden space-y-4">
            {tradesData?.trades.map((trade) => (
              <div
                key={trade.id}
                className="bg-white rounded-lg p-4 border border-slate-200"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-medium text-lg">{trade.symbol}</span>
                  <SideBadge side={trade.side} />
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-slate-500">Strategy</div>
                    <div className="font-medium text-slate-700">{trade.strategy}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Exit Time</div>
                    <div className="font-medium text-slate-700">
                      {new Date(trade.exit_time).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500">Entry Price</div>
                    <div className="font-medium">{(trade.entry_price ?? 0).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Exit Price</div>
                    <div className="font-medium">{(trade.exit_price ?? 0).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">P&L</div>
                    <div
                      className={`font-medium ${
                        pnlTone(trade.pnl)
                      }`}
                    >
                      {(trade.pnl ?? 0) >= 0 ? '+' : ''}
                      {(trade.pnl ?? 0).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500">P&L %</div>
                    <div
                      className={`font-medium ${
                        pnlTone(trade.pnl_pct)
                      }`}
                    >
                      {(trade.pnl_pct ?? 0) >= 0 ? '+' : ''}
                      {(trade.pnl_pct ?? 0).toFixed(2)}%
                    </div>
                  </div>
                </div>
                <LifecycleTextButton
                  label={`View lifecycle for ${trade.symbol}`}
                  onClick={() => setSelectedLifecycleTrade(trade)}
                />
              </div>
            ))}
          </div>

          {/* Desktop Table View with Horizontal Scroll */}
          <div className="hidden md:block bg-white rounded-lg overflow-hidden border border-slate-200">
            <div className="overflow-x-auto">
              <table className="min-w-[900px] w-full">
                <caption className="sr-only">Live Redis trades and lifecycle links</caption>
                <thead className="bg-slate-100">
                  <tr>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Exit Time</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Strategy</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Symbol</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Side</th>
                    <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">Entry</th>
                    <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">Exit</th>
                    <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">P&L</th>
                    <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">P&L %</th>
                    <th scope="col" className="px-4 py-3 text-center text-sm font-medium text-slate-700">Lifecycle</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {tradesData?.trades.map((trade) => (
                    <tr key={trade.id} className="hover:bg-slate-100">
                      <td className="px-4 py-3 text-sm text-slate-500">
                        {new Date(trade.exit_time).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">{trade.strategy}</td>
                      <td className="px-4 py-3 font-medium">{trade.symbol}</td>
                      <td className="px-4 py-3">
                        <SideBadge side={trade.side} />
                      </td>
                      <td className="px-4 py-3 text-right">{(trade.entry_price ?? 0).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">{(trade.exit_price ?? 0).toLocaleString()}</td>
                      <td
                        className={`px-4 py-3 text-right font-medium ${
                          pnlTone(trade.pnl)
                        }`}
                      >
                        {(trade.pnl ?? 0) >= 0 ? '+' : ''}
                        {(trade.pnl ?? 0).toLocaleString()}
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-medium ${
                          pnlTone(trade.pnl_pct)
                        }`}
                      >
                        {(trade.pnl_pct ?? 0) >= 0 ? '+' : ''}
                        {(trade.pnl_pct ?? 0).toFixed(2)}%
                      </td>
                      <td className="px-4 py-3 text-center">
                        <LifecycleIconButton
                          label={`View lifecycle for ${trade.symbol}`}
                          onClick={() => setSelectedLifecycleTrade(trade)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function HistoryTab() {
  const { selectedAsset } = useAssetClass();
  const [selectedLifecycleTrade, setSelectedLifecycleTrade] = useState<DbTrade | null>(null);

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
    dataUpdatedAt: statsUpdatedAt,
    isRefetching: statsRefetching,
  } = useQuery<DbStats>({
    queryKey: ['db-statistics', selectedAsset],
    queryFn: async () => {
      const r = await tradesApi.getClosedStatistics({ asset_class: selectedAsset });
      return r.data;
    },
    refetchInterval: QUERY_INTERVALS_MS.slow,
  });

  const {
    data: trades,
    isLoading: tradesLoading,
    error: tradesError,
    refetch: refetchTrades,
  } = useQuery<DbTrade[]>({
    queryKey: ['db-trades', selectedAsset],
    queryFn: async () => {
      const r = await tradesApi.getClosedTrades({ asset_class: selectedAsset, limit: 100 });
      return Array.isArray(r.data) ? r.data : [];
    },
    refetchInterval: QUERY_INTERVALS_MS.slow,
  });

  const {
    data: openPositions,
    isLoading: positionsLoading,
    error: positionsError,
    refetch: refetchPositions,
  } = useQuery<DbOpenPosition[]>({
    queryKey: ['db-open-positions', selectedAsset],
    queryFn: () =>
      tradingApi
        .getPositions({ asset_class: selectedAsset })
        .then((r) => (Array.isArray(r.data) ? r.data : [])),
    refetchInterval: QUERY_INTERVALS_MS.fast,
  });

  const {
    data: lifecycleData,
    isLoading: lifecycleLoading,
    error: lifecycleError,
    refetch: refetchLifecycle,
  } = useQuery<TradeLifecycleResponse>({
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

  const isLoading = statsLoading || tradesLoading;
  const hasError = statsError || tradesError || positionsError;

  // Error state
  if (hasError && !isLoading) {
    const errorMsg = statsError instanceof Error
      ? statsError.message
      : tradesError instanceof Error
        ? tradesError.message
        : positionsError instanceof Error
          ? positionsError.message
          : 'Failed to load data';
    return (
      <ErrorMessage
        message={errorMsg}
        onRetry={() => {
          if (statsError) refetchStats();
          if (tradesError) refetchTrades();
          if (positionsError) refetchPositions();
        }}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div role="status" aria-label="Loading trade history" className="sr-only">
          Loading trade history
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4">
          {Array.from({ length: 4 }).map((_, idx) => (
            <div key={idx} className="bg-white rounded-lg p-4 border border-slate-200">
              <div className="h-4 bg-slate-100 rounded animate-pulse w-20 mb-2" />
              <div className="h-6 bg-slate-100 rounded animate-pulse w-24" />
            </div>
          ))}
        </div>
        <TableSkeleton rows={10} columns={10} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Refresh Indicator */}
      <div className="flex justify-end">
        <div className="flex items-center gap-2">
          <RefreshIndicator
            lastUpdated={statsUpdatedAt}
            isRefreshing={statsRefetching}
            showStaleWarning={true}
            staleThresholdSeconds={60}
          />
          <button
            type="button"
            onClick={() => {
              refetchStats();
              refetchTrades();
              refetchPositions();
            }}
            className="inline-flex h-9 w-9 items-center justify-center rounded border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-900"
            aria-label="Refresh trade history"
          >
            <RefreshCcw className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4">
          <StatCard title="Total Trades" value={String(stats.total_trades)} />
          <StatCard
            title="Win Rate"
            value={`${(stats.win_rate ?? 0).toFixed(1)}%`}
            variant={(stats.win_rate ?? 0) >= 50 ? 'positive' : 'negative'}
          />
          <StatCard
            title="Total P&L"
            value={`${(stats.total_pnl ?? 0) >= 0 ? '+' : ''}${(stats.total_pnl ?? 0).toLocaleString()}`}
            variant={(stats.total_pnl ?? 0) >= 0 ? 'positive' : 'negative'}
          />
          <StatCard
            title="Avg P&L"
            value={`${(stats.avg_pnl ?? 0) >= 0 ? '+' : ''}${(stats.avg_pnl ?? 0).toLocaleString()}`}
            variant={(stats.avg_pnl ?? 0) >= 0 ? 'positive' : 'negative'}
          />
        </div>
      )}

      {selectedLifecycleTrade ? (
        <LifecycleTimeline
          title={`Lifecycle ${selectedLifecycleTrade.code}`}
          data={lifecycleData}
          isLoading={lifecycleLoading}
          error={
            lifecycleError instanceof Error
              ? lifecycleError.message
              : lifecycleError
                ? 'Failed to load lifecycle'
                : null
          }
          onRetry={() => refetchLifecycle()}
          onClose={() => setSelectedLifecycleTrade(null)}
        />
      ) : null}

      {/* Open Positions */}
      {positionsLoading ? (
        <div>
          <h3 className="text-lg font-medium mb-3">Open Positions</h3>
          <TableSkeleton rows={3} columns={10} />
        </div>
      ) : positionsError ? (
        <ErrorMessage
          message="Failed to load open positions"
          onRetry={() => refetchPositions()}
        />
      ) : openPositions && openPositions.length > 0 ? (
        <div>
          <h3 className="text-lg font-medium mb-3">Open Positions ({openPositions.length})</h3>

          {/* Mobile Card View */}
          <div className="block md:hidden space-y-4">
            {openPositions.map((pos) => (
              <div
                key={pos.id}
                className="bg-white rounded-lg p-4 border border-slate-200"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-medium text-lg">{pos.code}</span>
                  <SideBadge side={pos.side} />
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-slate-500">Name</div>
                    <div className="font-medium text-slate-700">{pos.name}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Strategy</div>
                    <div className="font-medium text-slate-700">{pos.strategy}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Entry Date</div>
                    <div className="font-medium">
                      {new Date(pos.entry_date).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500">Entry Price</div>
                    <div className="font-medium">{(pos.entry_price ?? 0).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Quantity</div>
                    <div className="font-medium">{pos.quantity}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">State</div>
                    <div>
                      <span className="px-2 py-1 rounded text-xs font-medium bg-blue-900 text-blue-300">
                        {pos.current_state}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500">High</div>
                    <div className="font-medium">{(pos.high_since_entry ?? 0).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Stop Loss</div>
                    <div className="font-medium">{(pos.stop_loss_price ?? 0).toLocaleString()}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Table View with Horizontal Scroll */}
          <div className="hidden md:block bg-white rounded-lg overflow-hidden border border-slate-200">
            <div className="overflow-x-auto">
              <table className="min-w-[1100px] w-full">
                <caption className="sr-only">Open database positions with risk state</caption>
                <thead className="bg-slate-100">
                  <tr>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Code</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Name</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Strategy</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Side</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Entry Date</th>
                    <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">Entry Price</th>
                    <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">Qty</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">State</th>
                    <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">High</th>
                    <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">Stop Loss</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {openPositions.map((pos) => (
                    <tr key={pos.id} className="hover:bg-slate-100">
                      <td className="px-4 py-3 font-medium">{pos.code}</td>
                      <td className="px-4 py-3">{pos.name}</td>
                      <td className="px-4 py-3">{pos.strategy}</td>
                      <td className="px-4 py-3">
                        <SideBadge side={pos.side} />
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500">
                        {new Date(pos.entry_date).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right">{(pos.entry_price ?? 0).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">{pos.quantity}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-1 rounded text-xs font-medium bg-blue-900 text-blue-300">
                          {pos.current_state}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">{(pos.high_since_entry ?? 0).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">{(pos.stop_loss_price ?? 0).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}

      {/* Closed Trades Table */}
      <div>
        <h3 className="text-lg font-medium mb-3">Closed Trades</h3>
        {!trades || trades.length === 0 ? (
          <div className="bg-white rounded-lg p-8 text-center text-slate-500">
            No closed trades in DB
          </div>
        ) : (
          <>
            {/* Mobile Card View */}
            <div className="block md:hidden space-y-4">
              {trades.map((trade) => (
                <div
                  key={trade.id}
                  className="bg-white rounded-lg p-4 border border-slate-200"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium text-lg">{trade.code}</span>
                    <SideBadge side={trade.side} />
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-slate-500">Name</div>
                      <div className="font-medium text-slate-700">{trade.name}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Strategy</div>
                      <div className="font-medium text-slate-700">{trade.strategy}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Exit Date</div>
                      <div className="font-medium">
                        {trade.exit_date ? new Date(trade.exit_date).toLocaleString() : '-'}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500">Exit Reason</div>
                      <div className="font-medium text-slate-700">{trade.exit_reason || '-'}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Entry Price</div>
                      <div className="font-medium">{(trade.entry_price ?? 0).toLocaleString()}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Exit Price</div>
                      <div className="font-medium">
                        {trade.exit_price ? (trade.exit_price ?? 0).toLocaleString() : '-'}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <div className="text-slate-500">P&L</div>
                      <div
                        className={`font-medium text-lg ${
                          pnlTone(trade.pnl)
                        }`}
                      >
                        {trade.pnl != null
                          ? `${(trade.pnl ?? 0) >= 0 ? '+' : ''}${(trade.pnl ?? 0).toLocaleString()}`
                          : '-'}
                      </div>
                    </div>
                  </div>
                  <LifecycleTextButton
                    label={`View lifecycle for ${trade.code}`}
                    onClick={() => setSelectedLifecycleTrade(trade)}
                  />
                </div>
              ))}
            </div>

            {/* Desktop Table View with Horizontal Scroll */}
            <div className="hidden md:block bg-white rounded-lg overflow-hidden border border-slate-200">
              <div className="overflow-x-auto">
                <table className="min-w-[1100px] w-full">
                  <caption className="sr-only">Closed database trades and lifecycle links</caption>
                  <thead className="bg-slate-100">
                    <tr>
                      <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Exit Date</th>
                      <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Code</th>
                      <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Name</th>
                      <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Strategy</th>
                      <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Side</th>
                      <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">Entry</th>
                      <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">Exit</th>
                      <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-slate-700">P&L</th>
                      <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Reason</th>
                      <th scope="col" className="px-4 py-3 text-center text-sm font-medium text-slate-700">Lifecycle</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {trades.map((trade) => (
                      <tr key={trade.id} className="hover:bg-slate-100">
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {trade.exit_date ? new Date(trade.exit_date).toLocaleString() : '-'}
                        </td>
                        <td className="px-4 py-3 font-medium">{trade.code}</td>
                        <td className="px-4 py-3">{trade.name}</td>
                        <td className="px-4 py-3">{trade.strategy}</td>
                        <td className="px-4 py-3">
                          <SideBadge side={trade.side} />
                        </td>
                        <td className="px-4 py-3 text-right">{(trade.entry_price ?? 0).toLocaleString()}</td>
                        <td className="px-4 py-3 text-right">
                          {trade.exit_price ? (trade.exit_price ?? 0).toLocaleString() : '-'}
                        </td>
                        <td
                          className={`px-4 py-3 text-right font-medium ${
                            pnlTone(trade.pnl)
                          }`}
                        >
                          {trade.pnl != null
                            ? `${(trade.pnl ?? 0) >= 0 ? '+' : ''}${(trade.pnl ?? 0).toLocaleString()}`
                            : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500">{trade.exit_reason || '-'}</td>
                        <td className="px-4 py-3 text-center">
                          <LifecycleIconButton
                            label={`View lifecycle for ${trade.code}`}
                            onClick={() => setSelectedLifecycleTrade(trade)}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Trades() {
  const [activeTab, setActiveTab] = useState<TabType>('live');
  const selectTab = (tab: TabType) => {
    setActiveTab(tab);
    document.getElementById(tab === 'live' ? 'trades-live-tab' : 'trades-history-tab')?.focus();
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      selectTab(activeTab === 'live' ? 'history' : 'live');
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      selectTab(activeTab === 'history' ? 'live' : 'history');
    } else if (event.key === 'Home') {
      event.preventDefault();
      selectTab('live');
    } else if (event.key === 'End') {
      event.preventDefault();
      selectTab('history');
    }
  };

  return (
    <>
      <HeaderBar />
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 lg:px-6 pt-2 pb-24 lg:pb-2">
        <div className="space-y-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="text-2xl font-bold">Trade History</h1>
            <div
              role="tablist"
              aria-label="Trade history data source"
              onKeyDown={handleTabKeyDown}
              className="flex w-fit rounded-lg overflow-hidden border border-slate-300"
            >
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'live'}
                aria-controls="trades-live-panel"
                id="trades-live-tab"
                onClick={() => selectTab('live')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === 'live'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                Live (Redis)
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'history'}
                aria-controls="trades-history-panel"
                id="trades-history-tab"
                onClick={() => selectTab('history')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === 'history'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                History (DB)
              </button>
            </div>
          </div>

          <div
            id={activeTab === 'live' ? 'trades-live-panel' : 'trades-history-panel'}
            role="tabpanel"
            aria-labelledby={activeTab === 'live' ? 'trades-live-tab' : 'trades-history-tab'}
          >
            {activeTab === 'live' ? <LiveTab /> : <HistoryTab />}
          </div>
        </div>
      </div>
    </>
  );
}

export default Trades;
