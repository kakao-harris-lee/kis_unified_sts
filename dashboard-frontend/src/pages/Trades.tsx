import { useState } from 'react';
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
import { tradesApi } from '../api/client';
import TableSkeleton from '../components/TableSkeleton';
import RefreshIndicator from '../components/RefreshIndicator';
import ErrorMessage from '../components/ErrorMessage';

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

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="text-xs text-gray-400 uppercase tracking-wide">{label}</div>
      <div className={`text-xl font-bold mt-1 ${color || 'text-white'}`}>{value}</div>
    </div>
  );
}

function LiveTab() {
  const [strategyFilter, setStrategyFilter] = useState<string>('');

  const {
    data: tradesData,
    isLoading: tradesLoading,
    error: tradesError,
    refetch: refetchTrades,
    dataUpdatedAt: tradesUpdatedAt,
    isRefetching: tradesRefetching,
  } = useQuery<TradesResponse>({
    queryKey: ['trades', strategyFilter],
    queryFn: () =>
      tradesApi
        .getTrades({
          strategy: strategyFilter || undefined,
          limit: 100,
        })
        .then((r) => r.data),
    refetchInterval: 10000,
  });

  const {
    data: byStrategy,
    error: strategyError,
    refetch: refetchStrategy,
  } = useQuery<StrategyStats[]>({
    queryKey: ['trades-by-strategy'],
    queryFn: () => tradesApi.getByStrategy().then((r) => r.data),
    refetchInterval: 10000,
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
        <select
          value={strategyFilter}
          onChange={(e) => setStrategyFilter(e.target.value)}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
        >
          <option value="">All Strategies</option>
          <option value="bb_reversion">BB Reversion</option>
          <option value="volume_accumulation">Volume Accumulation</option>
          <option value="opening_volume_surge">Opening Volume Surge</option>
        </select>
        <div className="flex items-center gap-4">
          <RefreshIndicator
            lastUpdated={tradesUpdatedAt}
            isRefreshing={tradesRefetching}
            showStaleWarning={true}
            staleThresholdSeconds={30}
          />
          <div className="text-sm text-gray-400">{tradesData?.total || 0} trade(s)</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Cumulative P&L (%)</h3>
          {tradesLoading ? (
            <div className="h-[250px] flex items-center justify-center">
              <div className="animate-pulse text-gray-400">Loading chart...</div>
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
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Performance by Strategy</h3>
          {tradesLoading || strategyError ? (
            <div className="h-[250px] flex items-center justify-center">
              {strategyError ? (
                <div className="text-center">
                  <div className="text-red-400 text-sm mb-2">Failed to load</div>
                  <button
                    onClick={() => refetchStrategy()}
                    className="text-xs text-blue-400 hover:text-blue-300"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <div className="animate-pulse text-gray-400">Loading chart...</div>
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

      {tradesLoading ? (
        <TableSkeleton rows={10} columns={8} />
      ) : tradesData?.trades.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-400">No trades found</div>
      ) : (
        <>
          {/* Mobile Card View */}
          <div className="block md:hidden space-y-4">
            {tradesData?.trades.map((trade) => (
              <div
                key={trade.id}
                className="bg-gray-800 rounded-lg p-4 border border-gray-700"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-medium text-lg">{trade.symbol}</span>
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium ${
                      trade.side === 'BUY'
                        ? 'bg-green-900 text-green-300'
                        : 'bg-red-900 text-red-300'
                    }`}
                  >
                    {trade.side}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-gray-400">Strategy</div>
                    <div className="font-medium text-gray-300">{trade.strategy}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">Exit Time</div>
                    <div className="font-medium text-gray-300">
                      {new Date(trade.exit_time).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Entry Price</div>
                    <div className="font-medium">{trade.entry_price.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">Exit Price</div>
                    <div className="font-medium">{trade.exit_price.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">P&L</div>
                    <div
                      className={`font-medium ${
                        trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {trade.pnl >= 0 ? '+' : ''}
                      {trade.pnl.toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">P&L %</div>
                    <div
                      className={`font-medium ${
                        trade.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {trade.pnl_pct >= 0 ? '+' : ''}
                      {trade.pnl_pct.toFixed(2)}%
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Table View with Horizontal Scroll */}
          <div className="hidden md:block bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-700">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Exit Time</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Strategy</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Symbol</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Side</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Entry</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Exit</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">P&L</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">P&L %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {tradesData?.trades.map((trade) => (
                    <tr key={trade.id} className="hover:bg-gray-750">
                      <td className="px-4 py-3 text-sm text-gray-400">
                        {new Date(trade.exit_time).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">{trade.strategy}</td>
                      <td className="px-4 py-3 font-medium">{trade.symbol}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            trade.side === 'BUY'
                              ? 'bg-green-900 text-green-300'
                              : 'bg-red-900 text-red-300'
                          }`}
                        >
                          {trade.side}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">{trade.entry_price.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">{trade.exit_price.toLocaleString()}</td>
                      <td
                        className={`px-4 py-3 text-right font-medium ${
                          trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {trade.pnl >= 0 ? '+' : ''}
                        {trade.pnl.toLocaleString()}
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-medium ${
                          trade.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {trade.pnl_pct >= 0 ? '+' : ''}
                        {trade.pnl_pct.toFixed(2)}%
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
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
    dataUpdatedAt: statsUpdatedAt,
    isRefetching: statsRefetching,
  } = useQuery<DbStats>({
    queryKey: ['db-statistics'],
    queryFn: () => tradesApi.getDbStatistics().then((r) => r.data),
    refetchInterval: 30000,
  });

  const {
    data: trades,
    isLoading: tradesLoading,
    error: tradesError,
    refetch: refetchTrades,
  } = useQuery<DbTrade[]>({
    queryKey: ['db-trades'],
    queryFn: () => tradesApi.getDbTrades({ limit: 100 }).then((r) => r.data),
    refetchInterval: 30000,
  });

  const {
    data: openPositions,
    isLoading: positionsLoading,
    error: positionsError,
    refetch: refetchPositions,
  } = useQuery<DbOpenPosition[]>({
    queryKey: ['db-open-positions'],
    queryFn: () => tradesApi.getDbOpenPositions().then((r) => r.data),
    refetchInterval: 10000,
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, idx) => (
            <div key={idx} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="h-4 bg-gray-700 rounded animate-pulse w-20 mb-2" />
              <div className="h-6 bg-gray-700 rounded animate-pulse w-24" />
            </div>
          ))}
        </div>
        <TableSkeleton rows={10} columns={9} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Refresh Indicator */}
      <div className="flex justify-end">
        <RefreshIndicator
          lastUpdated={statsUpdatedAt}
          isRefreshing={statsRefetching}
          showStaleWarning={true}
          staleThresholdSeconds={60}
        />
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Trades" value={String(stats.total_trades)} />
          <StatCard
            label="Win Rate"
            value={`${stats.win_rate.toFixed(1)}%`}
            color={stats.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}
          />
          <StatCard
            label="Total P&L"
            value={`${stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl.toLocaleString()}`}
            color={stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}
          />
          <StatCard
            label="Avg P&L"
            value={`${stats.avg_pnl >= 0 ? '+' : ''}${stats.avg_pnl.toLocaleString()}`}
            color={stats.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}
          />
        </div>
      )}

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
                className="bg-gray-800 rounded-lg p-4 border border-gray-700"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-medium text-lg">{pos.code}</span>
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium ${
                      pos.side === 'long'
                        ? 'bg-green-900 text-green-300'
                        : 'bg-red-900 text-red-300'
                    }`}
                  >
                    {pos.side}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-gray-400">Name</div>
                    <div className="font-medium text-gray-300">{pos.name}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">Strategy</div>
                    <div className="font-medium text-gray-300">{pos.strategy}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">Entry Date</div>
                    <div className="font-medium">
                      {new Date(pos.entry_date).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Entry Price</div>
                    <div className="font-medium">{pos.entry_price.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">Quantity</div>
                    <div className="font-medium">{pos.quantity}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">State</div>
                    <div>
                      <span className="px-2 py-1 rounded text-xs font-medium bg-blue-900 text-blue-300">
                        {pos.current_state}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">High</div>
                    <div className="font-medium">{pos.high_since_entry.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">Stop Loss</div>
                    <div className="font-medium">{pos.stop_loss_price.toLocaleString()}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Table View with Horizontal Scroll */}
          <div className="hidden md:block bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-700">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Code</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Name</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Strategy</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Side</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Entry Date</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Entry Price</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Qty</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">State</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">High</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Stop Loss</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {openPositions.map((pos) => (
                    <tr key={pos.id} className="hover:bg-gray-750">
                      <td className="px-4 py-3 font-medium">{pos.code}</td>
                      <td className="px-4 py-3">{pos.name}</td>
                      <td className="px-4 py-3">{pos.strategy}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            pos.side === 'long'
                              ? 'bg-green-900 text-green-300'
                              : 'bg-red-900 text-red-300'
                          }`}
                        >
                          {pos.side}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-400">
                        {new Date(pos.entry_date).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right">{pos.entry_price.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">{pos.quantity}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-1 rounded text-xs font-medium bg-blue-900 text-blue-300">
                          {pos.current_state}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">{pos.high_since_entry.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">{pos.stop_loss_price.toLocaleString()}</td>
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
          <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-400">
            No closed trades in DB
          </div>
        ) : (
          <>
            {/* Mobile Card View */}
            <div className="block md:hidden space-y-4">
              {trades.map((trade) => (
                <div
                  key={trade.id}
                  className="bg-gray-800 rounded-lg p-4 border border-gray-700"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium text-lg">{trade.code}</span>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        trade.side === 'long'
                          ? 'bg-green-900 text-green-300'
                          : 'bg-red-900 text-red-300'
                      }`}
                    >
                      {trade.side}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-gray-400">Name</div>
                      <div className="font-medium text-gray-300">{trade.name}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Strategy</div>
                      <div className="font-medium text-gray-300">{trade.strategy}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Exit Date</div>
                      <div className="font-medium">
                        {trade.exit_date ? new Date(trade.exit_date).toLocaleString() : '-'}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400">Exit Reason</div>
                      <div className="font-medium text-gray-300">{trade.exit_reason || '-'}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Entry Price</div>
                      <div className="font-medium">{trade.entry_price.toLocaleString()}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Exit Price</div>
                      <div className="font-medium">
                        {trade.exit_price ? trade.exit_price.toLocaleString() : '-'}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <div className="text-gray-400">P&L</div>
                      <div
                        className={`font-medium text-lg ${
                          (trade.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {trade.pnl != null
                          ? `${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toLocaleString()}`
                          : '-'}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Desktop Table View with Horizontal Scroll */}
            <div className="hidden md:block bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Exit Date</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Code</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Name</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Strategy</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Side</th>
                      <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Entry</th>
                      <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">Exit</th>
                      <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">P&L</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {trades.map((trade) => (
                      <tr key={trade.id} className="hover:bg-gray-750">
                        <td className="px-4 py-3 text-sm text-gray-400">
                          {trade.exit_date ? new Date(trade.exit_date).toLocaleString() : '-'}
                        </td>
                        <td className="px-4 py-3 font-medium">{trade.code}</td>
                        <td className="px-4 py-3">{trade.name}</td>
                        <td className="px-4 py-3">{trade.strategy}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${
                              trade.side === 'long'
                                ? 'bg-green-900 text-green-300'
                                : 'bg-red-900 text-red-300'
                            }`}
                          >
                            {trade.side}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">{trade.entry_price.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right">
                          {trade.exit_price ? trade.exit_price.toLocaleString() : '-'}
                        </td>
                        <td
                          className={`px-4 py-3 text-right font-medium ${
                            (trade.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {trade.pnl != null
                            ? `${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toLocaleString()}`
                            : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-400">{trade.exit_reason || '-'}</td>
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trade History</h1>
        <div className="flex rounded-lg overflow-hidden border border-gray-600">
          <button
            onClick={() => setActiveTab('live')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'live'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            Live (Redis)
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'history'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            History (DB)
          </button>
        </div>
      </div>

      {activeTab === 'live' ? <LiveTab /> : <HistoryTab />}
    </div>
  );
}

export default Trades;
