"use client";

import { useState } from 'react';
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
import TableSkeleton from '@/components/dashboard/TableSkeleton';
import RefreshIndicator from '@/components/dashboard/RefreshIndicator';
import ErrorMessage from '@/components/dashboard/ErrorMessage';
import SideBadge from '@/components/dashboard/SideBadge';
import StrategySelect from '@/components/dashboard/StrategySelect';
import LifecycleTimeline from '@/components/dashboard/LifecycleTimeline';
import SymbolLabel, { symbolDisplayText } from '@/components/dashboard/SymbolLabel';
import { useHighlightParam } from '@/hooks/dashboard/useHighlightParam';
import {
  buildCumulativePnlData,
  pnlTone,
  useLiveTradesQueries,
  type Trade,
} from '../hooks';

// Ring applied to a row deep-linked via ?highlight=<trade_id>.
const HIGHLIGHT_RING = 'ring-2 ring-amber-500 ring-inset';
const liveTradeDomId = (id: string) => `trade-${id}`;

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

export function LiveTradesTab() {
  const [strategyFilter, setStrategyFilter] = useState<string>('');
  const [chartCollapsed, setChartCollapsed] = useState<boolean>(true);
  const [selectedLifecycleTrade, setSelectedLifecycleTrade] = useState<Trade | null>(null);
  const chartPanelId = 'live-trade-charts';
  const { selectedAsset, tradesQuery, lifecycleQuery, byStrategyQuery } = useLiveTradesQueries(
    strategyFilter,
    selectedLifecycleTrade
  );

  const {
    data: tradesData,
    isLoading: tradesLoading,
    error: tradesError,
    refetch: refetchTrades,
    dataUpdatedAt: tradesUpdatedAt,
    isRefetching: tradesRefetching,
  } = tradesQuery;
  const {
    data: lifecycleData,
    isLoading: lifecycleLoading,
    error: lifecycleError,
    refetch: refetchLifecycle,
  } = lifecycleQuery;
  const {
    data: byStrategy,
    error: strategyError,
    refetch: refetchStrategy,
  } = byStrategyQuery;

  const highlightId = useHighlightParam(
    liveTradeDomId,
    !!tradesData?.trades.length,
  );

  const cumulativePnlData = buildCumulativePnlData(tradesData?.trades);
  const selectedLifecycleLabel = selectedLifecycleTrade
    ? symbolDisplayText({
        code: selectedLifecycleTrade.symbol,
        name: selectedLifecycleTrade.name,
      })
    : '';

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
          title={`Lifecycle ${selectedLifecycleLabel}`}
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
                id={liveTradeDomId(trade.id)}
                className={`bg-white rounded-lg p-4 border border-slate-200 ${
                  highlightId === trade.id ? HIGHLIGHT_RING : ''
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <SymbolLabel
                    code={trade.symbol}
                    name={trade.name}
                    className="text-lg text-slate-900"
                  />
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
                  label={`View lifecycle for ${symbolDisplayText({
                    code: trade.symbol,
                    name: trade.name,
                  })}`}
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
                    <tr
                      key={trade.id}
                      id={liveTradeDomId(trade.id)}
                      className={`hover:bg-slate-100 ${
                        highlightId === trade.id ? HIGHLIGHT_RING : ''
                      }`}
                    >
                      <td className="px-4 py-3 text-sm text-slate-500">
                        {new Date(trade.exit_time).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">{trade.strategy}</td>
                      <td className="px-4 py-3 font-medium">
                        <SymbolLabel code={trade.symbol} name={trade.name} />
                      </td>
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
                          label={`View lifecycle for ${symbolDisplayText({
                            code: trade.symbol,
                            name: trade.name,
                          })}`}
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
