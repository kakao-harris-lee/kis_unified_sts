import { useEffect, useState } from 'react';
import { signalsApi } from '../api/client';
import TableSkeleton from '../components/TableSkeleton';
import RefreshIndicator from '../components/RefreshIndicator';
import ErrorMessage from '../components/ErrorMessage';
import StrategySelect from '../components/StrategySelect';
import useQueryWithError from '../hooks/useQueryWithError';
import SideBadge from '../components/SideBadge';
import HeaderBar from '../components/HeaderBar';
import BottomSheet from '../components/BottomSheet';
import { useAssetClass } from '../contexts/AssetClassContext';

interface Signal {
  id: string;
  strategy: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  strength: number;
  price: number;
  timestamp: string;
  executed: boolean;
}

interface SignalsResponse {
  signals: Signal[];
  total: number;
}

function Signals() {
  const { selectedAsset } = useAssetClass();
  const [strategyFilter, setStrategyFilter] = useState<string>('');
  const [sideFilter, setSideFilter] = useState<string>('');
  const [filterSheetOpen, setFilterSheetOpen] = useState<boolean>(false);

  // Reset filters when asset class changes - strategies are asset-specific
  useEffect(() => {
    setStrategyFilter('');
    setSideFilter('');
  }, [selectedAsset]);

  const { data, isLoading, errorMessage, refetch, isRefetching, dataUpdatedAt } =
    useQueryWithError<SignalsResponse>({
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
      refetchInterval: 5000,
    });

  const filterControls = (
    <>
      <div>
        <label className="block text-sm text-gray-400 mb-1">Strategy</label>
        <StrategySelect value={strategyFilter} onChange={setStrategyFilter} />
      </div>
      <div>
        <label className="block text-sm text-gray-400 mb-1">Side</label>
        <select
          value={sideFilter}
          onChange={(e) => setSideFilter(e.target.value)}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
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
              <div className="text-sm text-gray-400">{data?.total || 0} signal(s)</div>
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
              className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded text-sm text-left text-gray-200"
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

          {/* Signals Table */}
          {isLoading ? (
            <TableSkeleton rows={10} columns={7} />
          ) : errorMessage ? (
            <ErrorMessage message={errorMessage} onRetry={() => refetch()} />
          ) : data?.signals.length === 0 ? (
            <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-400">
              No signals found
            </div>
          ) : (
            <>
              {/* Mobile Card View */}
              <div className="block md:hidden space-y-4">
                {data?.signals.map((signal) => (
                  <div
                    key={signal.id}
                    className="bg-gray-800 rounded-lg p-4 border border-gray-700"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium text-lg">{signal.symbol}</span>
                      <SideBadge side={signal.side} />
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <div className="text-gray-400">Time</div>
                        <div className="font-medium text-xs">
                          {new Date(signal.timestamp).toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-400">Strategy</div>
                        <div className="font-medium">{signal.strategy}</div>
                      </div>
                      <div>
                        <div className="text-gray-400">Price</div>
                        <div className="font-medium">
                          {signal.price.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-400">Executed</div>
                        <div className="font-medium">
                          {signal.executed ? (
                            <span className="text-green-400">Yes</span>
                          ) : (
                            <span className="text-gray-500">No</span>
                          )}
                        </div>
                      </div>
                      <div className="col-span-2">
                        <div className="text-gray-400 mb-1">Strength</div>
                        <div className="flex items-center">
                          <div className="flex-1 bg-gray-700 rounded-full h-2 mr-2">
                            <div
                              className="bg-blue-500 h-2 rounded-full"
                              style={{ width: `${(signal.strength ?? 0) * 100}%` }}
                            />
                          </div>
                          <span className="text-sm font-medium">
                            {((signal.strength ?? 0) * 100).toFixed(0)}%
                          </span>
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
                        <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                          Time
                        </th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                          Strategy
                        </th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                          Symbol
                        </th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                          Side
                        </th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                          Price
                        </th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                          Strength
                        </th>
                        <th className="px-4 py-3 text-center text-sm font-medium text-gray-300">
                          Executed
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                      {data?.signals.map((signal) => (
                        <tr key={signal.id} className="hover:bg-gray-750">
                          <td className="px-4 py-3 text-sm text-gray-400">
                            {new Date(signal.timestamp).toLocaleString()}
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
                              <div className="w-16 bg-gray-700 rounded-full h-2 mr-2">
                                <div
                                  className="bg-blue-500 h-2 rounded-full"
                                  style={{ width: `${(signal.strength ?? 0) * 100}%` }}
                                />
                              </div>
                              <span className="text-sm">
                                {((signal.strength ?? 0) * 100).toFixed(0)}%
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center">
                            {signal.executed ? (
                              <span className="text-green-400">Yes</span>
                            ) : (
                              <span className="text-gray-500">-</span>
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
