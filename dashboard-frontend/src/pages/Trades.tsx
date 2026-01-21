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

function Trades() {
  const [strategyFilter, setStrategyFilter] = useState<string>('');

  const { data: tradesData, isLoading: tradesLoading } = useQuery<TradesResponse>({
    queryKey: ['trades', strategyFilter],
    queryFn: () =>
      tradesApi
        .getTrades({
          strategy: strategyFilter || undefined,
          limit: 100,
        })
        .then((r) => r.data),
  });

  const { data: byStrategy } = useQuery<StrategyStats[]>({
    queryKey: ['trades-by-strategy'],
    queryFn: () => tradesApi.getByStrategy().then((r) => r.data),
  });

  // Prepare cumulative PnL data for chart
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

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trade History</h1>
        <div className="flex items-center space-x-4">
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
          <div className="text-sm text-gray-400">
            {tradesData?.total || 0} trade(s)
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cumulative PnL Chart */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Cumulative P&L (%)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={cumulativePnlData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="idx" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #374151',
                }}
              />
              <Line
                type="monotone"
                dataKey="cumPnl"
                stroke="#10B981"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Strategy Performance Chart */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Performance by Strategy</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={byStrategy || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="strategy" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #374151',
                }}
              />
              <Bar dataKey="total_pnl" fill="#3B82F6" name="Total P&L %" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Trades Table */}
      {tradesLoading ? (
        <div className="bg-gray-800 rounded-lg p-8 text-center">
          <div className="animate-pulse text-gray-400">Loading trades...</div>
        </div>
      ) : tradesData?.trades.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-400">
          No trades found
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
          <table className="w-full">
            <thead className="bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                  Exit Time
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
                  Entry
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                  Exit
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                  P&L
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                  P&L %
                </th>
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
                  <td className="px-4 py-3 text-right">
                    {trade.entry_price.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {trade.exit_price.toLocaleString()}
                  </td>
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
      )}
    </div>
  );
}

export default Trades;
