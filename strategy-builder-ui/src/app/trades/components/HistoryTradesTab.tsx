"use client";

import { useState } from 'react';
import { Clock3, RefreshCcw } from 'lucide-react';
import TableSkeleton from '@/components/dashboard/TableSkeleton';
import RefreshIndicator from '@/components/dashboard/RefreshIndicator';
import ErrorMessage from '@/components/dashboard/ErrorMessage';
import SideBadge from '@/components/dashboard/SideBadge';
import StatCard from '@/components/dashboard/StatCard';
import LifecycleTimeline from '@/components/dashboard/LifecycleTimeline';
import SymbolLabel, { symbolDisplayText } from '@/components/dashboard/SymbolLabel';
import { useHighlightParam } from '@/hooks/dashboard/useHighlightParam';
import {
  pnlTone,
  useHistoryTradesQueries,
  type DbTrade,
} from '../hooks';

// Ring applied to a row deep-linked via ?highlight=<trade_id>.
const HIGHLIGHT_RING = 'ring-2 ring-amber-500 ring-inset';
const historyTradeDomId = (id: string) => `trade-${id}`;

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

export function HistoryTradesTab() {
  const [selectedLifecycleTrade, setSelectedLifecycleTrade] = useState<DbTrade | null>(null);
  const { statsQuery, tradesQuery, openPositionsQuery, lifecycleQuery } =
    useHistoryTradesQueries(selectedLifecycleTrade);

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
    dataUpdatedAt: statsUpdatedAt,
    isRefetching: statsRefetching,
  } = statsQuery;
  const {
    data: trades,
    isLoading: tradesLoading,
    error: tradesError,
    refetch: refetchTrades,
  } = tradesQuery;
  const {
    data: openPositions,
    isLoading: positionsLoading,
    error: positionsError,
    refetch: refetchPositions,
  } = openPositionsQuery;
  const {
    data: lifecycleData,
    isLoading: lifecycleLoading,
    error: lifecycleError,
    refetch: refetchLifecycle,
  } = lifecycleQuery;

  const highlightId = useHighlightParam(historyTradeDomId, !!trades?.length);

  const isLoading = statsLoading || tradesLoading;
  const hasError = statsError || tradesError || positionsError;
  const selectedLifecycleLabel = selectedLifecycleTrade
    ? symbolDisplayText({
        code: selectedLifecycleTrade.code,
        name: selectedLifecycleTrade.name,
      })
    : '';

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
                  <SymbolLabel
                    code={pos.code}
                    name={pos.name}
                    className="text-lg text-slate-900"
                  />
                  <SideBadge side={pos.side} />
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
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
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Symbol</th>
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
                      <td className="px-4 py-3 font-medium">
                        <SymbolLabel code={pos.code} name={pos.name} />
                      </td>
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
                  id={historyTradeDomId(trade.id)}
                  className={`bg-white rounded-lg p-4 border border-slate-200 ${
                    highlightId === trade.id ? HIGHLIGHT_RING : ''
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <SymbolLabel
                      code={trade.code}
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
                    label={`View lifecycle for ${symbolDisplayText({
                      code: trade.code,
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
                <table className="min-w-[1100px] w-full">
                  <caption className="sr-only">Closed database trades and lifecycle links</caption>
                  <thead className="bg-slate-100">
                    <tr>
                      <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Exit Date</th>
                      <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-slate-700">Symbol</th>
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
                      <tr
                        key={trade.id}
                        id={historyTradeDomId(trade.id)}
                        className={`hover:bg-slate-100 ${
                          highlightId === trade.id ? HIGHLIGHT_RING : ''
                        }`}
                      >
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {trade.exit_date ? new Date(trade.exit_date).toLocaleString() : '-'}
                        </td>
                        <td className="px-4 py-3 font-medium">
                          <SymbolLabel code={trade.code} name={trade.name} />
                        </td>
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
                            label={`View lifecycle for ${symbolDisplayText({
                              code: trade.code,
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
    </div>
  );
}
