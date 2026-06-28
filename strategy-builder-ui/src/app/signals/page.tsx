"use client";

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { decisionTraceApi, signalsApi } from '@/lib/dashboard/api';
import TableSkeleton from '@/components/dashboard/TableSkeleton';
import RefreshIndicator from '@/components/dashboard/RefreshIndicator';
import ErrorMessage from '@/components/dashboard/ErrorMessage';
import StrategySelect from '@/components/dashboard/StrategySelect';
import useQueryWithError from '@/hooks/dashboard/useQueryWithError';
import SideBadge from '@/components/dashboard/SideBadge';
import HeaderBar from '@/components/dashboard/HeaderBar';
import BottomSheet from '@/components/dashboard/BottomSheet';
import { useAssetClass } from '@/contexts/dashboard/AssetClassContext';
import { QUERY_INTERVALS_MS } from '@/lib/dashboard/queryIntervals';
import { formatKstDateTime } from '@/lib/dashboard/format';
import DecisionTracePanel from './components/DecisionTracePanel';
import type {
  DashboardSignal,
  DashboardSignalsResponse,
} from '@/lib/dashboard/signalTypes';

function displayPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'unknown';
  }
  return `${(value * 100).toFixed(0)}%`;
}

function strengthValue(signal: DashboardSignal) {
  return Math.max(0, Math.min(1, signal.strength ?? signal.confidence ?? 0));
}

function Signals() {
  const { selectedAsset } = useAssetClass();
  const [strategyFilter, setStrategyFilter] = useState<string>('');
  const [sideFilter, setSideFilter] = useState<string>('');
  const [filterSheetOpen, setFilterSheetOpen] = useState<boolean>(false);
  const [selectedSignal, setSelectedSignal] = useState<DashboardSignal | null>(null);

  // Reset filters when asset class changes - strategies are asset-specific.
  // Adjust state during render (React's recommended pattern) rather than in an
  // effect, which would trigger an extra render with the previous filters still
  // applied to the query.
  const [prevAsset, setPrevAsset] = useState(selectedAsset);
  if (selectedAsset !== prevAsset) {
    setPrevAsset(selectedAsset);
    setStrategyFilter('');
    setSideFilter('');
    setSelectedSignal(null);
  }

  const { data, isLoading, errorMessage, refetch, isRefetching, dataUpdatedAt } =
    useQueryWithError<DashboardSignalsResponse>({
      queryKey: ['signals', selectedAsset, strategyFilter, sideFilter],
      queryFn: () =>
        signalsApi
          .getSignals({
            asset_class: selectedAsset,
            strategy: strategyFilter || undefined,
            side: sideFilter || undefined,
            limit: 50,
          })
          .then((r) => r.data),
      refetchInterval: QUERY_INTERVALS_MS.normal,
    });

  const {
    data: traceData,
    isLoading: traceLoading,
    error: traceError,
    refetch: refetchTrace,
  } = useQuery({
    queryKey: ['signal-decision-trace', selectedAsset, selectedSignal?.id],
    queryFn: () =>
      decisionTraceApi
        .getDecisionTrace(selectedSignal?.id || '', { asset_class: selectedAsset })
        .then((r) => r.data),
    enabled: Boolean(selectedSignal?.id),
    refetchInterval: false,
  });

  const traceErrorMessage =
    traceError instanceof Error
      ? traceError.message
      : traceError
        ? 'Failed to load decision trace'
        : null;

  const updateStrategyFilter = (value: string) => {
    setStrategyFilter(value);
    setSelectedSignal(null);
  };

  const updateSideFilter = (value: string) => {
    setSideFilter(value);
    setSelectedSignal(null);
  };

  const filterControls = (
    <>
      <div>
        <label className="block text-sm text-slate-500 mb-1">Strategy</label>
        <StrategySelect value={strategyFilter} onChange={updateStrategyFilter} />
      </div>
      <div>
        <label className="block text-sm text-slate-500 mb-1">Side</label>
        <select
          value={sideFilter}
          onChange={(e) => updateSideFilter(e.target.value)}
          className="bg-white border border-slate-300 rounded px-3 py-2 text-sm w-full"
        >
          <option value="">All</option>
          <option value="BUY">Buy</option>
          <option value="SELL">Sell</option>
        </select>
      </div>
    </>
  );

  const activeFilterCount =
    (strategyFilter ? 1 : 0) + (sideFilter ? 1 : 0);

  return (
    <>
      <HeaderBar />
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 lg:px-6 pt-2 pb-24 lg:pb-2">
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">Trading Signals</h1>
            <div className="flex items-center gap-4">
              <div className="text-sm text-slate-500">{data?.total || 0} signal(s)</div>
              <RefreshIndicator
                lastUpdated={dataUpdatedAt}
                isRefreshing={isRefetching}
                showStaleWarning={true}
                staleThresholdSeconds={30}
              />
            </div>
          </div>

          {/* Desktop Filters */}
          <div className="hidden sm:flex space-x-4">{filterControls}</div>

          {/* Mobile Filter Button */}
          <div className="sm:hidden">
            <button
              onClick={() => setFilterSheetOpen(true)}
              className="w-full px-4 py-2 bg-white border border-slate-300 rounded text-sm text-left text-slate-800"
            >
              <span className="mr-2">⚙</span>
              필터
              {activeFilterCount > 0 && (
                <span className="ml-2 px-2 py-0.5 bg-blue-600 text-white text-xs rounded-full">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>

          <BottomSheet
            open={filterSheetOpen}
            onClose={() => setFilterSheetOpen(false)}
            title="필터"
          >
            <div className="space-y-4">{filterControls}</div>
          </BottomSheet>

          {selectedSignal ? (
            <DecisionTracePanel
              trace={traceData}
              isLoading={traceLoading}
              error={traceErrorMessage}
              onClose={() => setSelectedSignal(null)}
              onRefresh={() => refetchTrace()}
            />
          ) : null}

          {/* Signals Table */}
          {isLoading ? (
            <TableSkeleton rows={10} columns={7} />
          ) : errorMessage ? (
            <ErrorMessage message={errorMessage} onRetry={() => refetch()} />
          ) : data?.signals.length === 0 ? (
            <div className="bg-white rounded-lg p-8 text-center text-slate-500">
              No signals found
            </div>
          ) : (
            <>
              {/* Mobile Card View */}
              <div className="block md:hidden space-y-4">
                {data?.signals.map((signal) => (
                  <div
                    key={signal.id}
                    className="bg-white rounded-lg p-4 border border-slate-200"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium text-lg">{signal.symbol}</span>
                      <SideBadge side={signal.side} />
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <div className="text-slate-500">Time</div>
                        <div className="font-medium text-xs">
                          {formatKstDateTime(signal.timestamp)}
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-500">Strategy</div>
                        <div className="font-medium">{signal.strategy}</div>
                      </div>
                      <div>
                        <div className="text-slate-500">Price</div>
                        <div className="font-medium">
                          {signal.price.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-500">Executed</div>
                        <div className="font-medium">
                          {signal.executed ? (
                            <span className="text-green-400">Yes</span>
                          ) : (
                            <span className="text-slate-500">No</span>
                          )}
                        </div>
                      </div>
                      <div className="col-span-2">
                        <div className="text-slate-500 mb-1">Strength</div>
                        <div className="flex items-center">
                          <div className="flex-1 bg-slate-100 rounded-full h-2 mr-2">
                            <div
                              className="bg-blue-500 h-2 rounded-full"
                              style={{ width: `${strengthValue(signal) * 100}%` }}
                            />
                          </div>
                          <span className="text-sm font-medium">
                            {displayPercent(signal.strength ?? signal.confidence)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedSignal(signal)}
                      aria-label={`View trace for ${signal.symbol}`}
                      className="mt-4 w-full rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
                    >
                      View trace
                    </button>
                  </div>
                ))}
              </div>

              {/* Desktop Table View with Horizontal Scroll */}
              <div className="hidden md:block bg-white rounded-lg overflow-hidden border border-slate-200">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-100">
                      <tr>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                          Time
                        </th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                          Strategy
                        </th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                          Symbol
                        </th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-slate-700">
                          Side
                        </th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-slate-700">
                          Price
                        </th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-slate-700">
                          Strength
                        </th>
                        <th className="px-4 py-3 text-center text-sm font-medium text-slate-700">
                          Executed
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {data?.signals.map((signal) => (
                        <tr
                          key={signal.id}
                          className="cursor-pointer hover:bg-slate-100"
                          onClick={() => setSelectedSignal(signal)}
                          tabIndex={0}
                          role="button"
                          aria-label={`View trace for ${signal.symbol}`}
                          aria-pressed={selectedSignal?.id === signal.id}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault();
                              setSelectedSignal(signal);
                            }
                          }}
                        >
                          <td className="px-4 py-3 text-sm text-slate-500">
                            {formatKstDateTime(signal.timestamp)}
                          </td>
                          <td className="px-4 py-3">{signal.strategy}</td>
                          <td className="px-4 py-3 font-medium">{signal.symbol}</td>
                          <td className="px-4 py-3">
                            <SideBadge side={signal.side} />
                          </td>
                          <td className="px-4 py-3 text-right">
                            {signal.price.toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end">
                              <div className="w-16 bg-slate-100 rounded-full h-2 mr-2">
                                <div
                                  className="bg-blue-500 h-2 rounded-full"
                                  style={{ width: `${strengthValue(signal) * 100}%` }}
                                />
                              </div>
                              <span className="text-sm">
                                {displayPercent(signal.strength ?? signal.confidence)}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center">
                            {signal.executed ? (
                              <span className="text-green-400">Yes</span>
                            ) : (
                              <span className="text-slate-500">-</span>
                            )}
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
    </>
  );
}

export default Signals;
