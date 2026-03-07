import { useState } from 'react';
import { signalsApi } from '../api/client';
import TableSkeleton from '../components/TableSkeleton';
import RefreshIndicator from '../components/RefreshIndicator';
import ErrorMessage from '../components/ErrorMessage';
import useQueryWithError from '../hooks/useQueryWithError';
import SideBadge from '../components/SideBadge';

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
  const [strategyFilter, setStrategyFilter] = useState<string>('');
  const [sideFilter, setSideFilter] = useState<string>('');

  const { data, isLoading, errorMessage, refetch, isRefetching, dataUpdatedAt } =
    useQueryWithError<SignalsResponse>({
      queryKey: ['signals', strategyFilter, sideFilter],
      queryFn: () =>
        signalsApi
          .getSignals({
            strategy: strategyFilter || undefined,
            side: sideFilter || undefined,
            limit: 50,
          })
          .then((r) => r.data),
      refetchInterval: 5000,
    });

  return (
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

      {/* Filters */}
      <div className="flex space-x-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Strategy</label>
          <select
            value={strategyFilter}
            onChange={(e) => setStrategyFilter(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
          >
            <option value="">All Strategies</option>
            <option value="bb_reversion">BB Reversion</option>
            <option value="volume_momentum">Volume Momentum</option>
            <option value="pure_micro">Pure Micro</option>
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Side</label>
          <select
            value={sideFilter}
            onChange={(e) => setSideFilter(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm"
          >
            <option value="">All</option>
            <option value="BUY">Buy</option>
            <option value="SELL">Sell</option>
          </select>
        </div>
      </div>

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
        <div className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
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
                          style={{ width: `${signal.strength * 100}%` }}
                        />
                      </div>
                      <span className="text-sm">
                        {(signal.strength * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {signal.executed ? (
                      <span className="text-green-400">✓</span>
                    ) : (
                      <span className="text-gray-500">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default Signals;
