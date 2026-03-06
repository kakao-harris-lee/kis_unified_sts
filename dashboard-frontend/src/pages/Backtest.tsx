import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { backtestApi } from '../api/client';
import ErrorMessage from '../components/ErrorMessage';
import TableSkeleton from '../components/TableSkeleton';

interface BacktestRunResponse {
  run_id: string;
  status: string;
  result: BacktestResult;
}

interface BacktestResult {
  run_id: string;
  status: string;
  asset_class: string;
  strategy: string;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_capital: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
  win_rate: number;
  chart_image?: string | null;
  created_at: string;
  completed_at?: string | null;
}

interface BacktestListResponse {
  runs: BacktestResult[];
  total: number;
  page: number;
  limit: number;
}

const strategyOptions = {
  stock: [
    { value: 'bb_reversion', label: 'BB Reversion' },
    { value: 'mean_reversion', label: 'Mean Reversion' },
    { value: 'v35_optimized', label: 'V35 Optimized' },
    { value: 'stochrsi_trend', label: 'StochRSI Trend' },
    { value: 'ma_crossover', label: 'MA Crossover' },
  ],
  futures: [
    { value: 'ma_crossover', label: 'MA Crossover' },
    { value: 'stochrsi_trend', label: 'StochRSI Trend' },
  ],
};

const futuresTableOptions = [
  { value: 'kospi_mini_1m', label: 'KOSPI Mini 1m' },
  { value: 'kospi200f_1m', label: 'KOSPI200 Futures 1m' },
  { value: 'kospi200_index_1m', label: 'KOSPI200 Index 1m' },
];

function Backtest() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [assetClass, setAssetClass] = useState<'stock' | 'futures'>('stock');
  const [strategy, setStrategy] = useState('bb_reversion');
  const [symbol, setSymbol] = useState('005930');
  const [futuresTable, setFuturesTable] = useState('kospi_mini_1m');
  const [startDate, setStartDate] = useState(
    new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString().slice(0, 10)
  );
  const [endDate, setEndDate] = useState(today);
  const [capital, setCapital] = useState(10000000);
  const queryClient = useQueryClient();

  const {
    data: history,
    isLoading: historyLoading,
    isError: historyError,
    error: historyErrorData,
    refetch: refetchHistory,
  } = useQuery<BacktestListResponse>({
    queryKey: ['backtest-history'],
    queryFn: () => backtestApi.list().then((r) => r.data),
  });

  const mutation = useMutation<BacktestRunResponse>({
    mutationFn: () =>
      backtestApi
        .run({
          asset_class: assetClass,
          strategy,
          symbol,
          start_date: startDate,
          end_date: endDate,
          initial_capital: capital,
          params:
            assetClass === 'futures' ? { table: futuresTable } : undefined,
        })
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-history'] });
    },
  });

  const result = mutation.data?.result;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Backtesting</h1>
      </div>

      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Asset</label>
            <select
              value={assetClass}
              onChange={(e) => {
                const next = e.target.value as 'stock' | 'futures';
                setAssetClass(next);
                const nextStrategy =
                  strategyOptions[next][0]?.value || 'ma_crossover';
                setStrategy(nextStrategy);
                setSymbol(next === 'stock' ? '005930' : 'A05601');
              }}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            >
              <option value="stock">Stock</option>
              <option value="futures">Futures</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            >
              {strategyOptions[assetClass].map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Symbol</label>
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            />
          </div>
          {assetClass === 'futures' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Futures Table
              </label>
              <select
                value={futuresTable}
                onChange={(e) => setFuturesTable(e.target.value)}
                className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
              >
                {futuresTableOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Start</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">End</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Initial Capital
            </label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm w-full"
            />
          </div>
        </div>
        <button
          onClick={() => mutation.mutate()}
          className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-500 disabled:opacity-50"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Running...' : 'Run Backtest'}
        </button>
        {mutation.isError && (
          <ErrorMessage
            message={
              mutation.error instanceof Error
                ? mutation.error.message
                : 'Failed to run backtest. Check inputs or data availability.'
            }
            onRetry={() => mutation.mutate()}
          />
        )}
      </div>

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400">Total Return</div>
              <div className="text-xl font-bold">
                {result.total_return_pct.toFixed(2)}%
              </div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400">Sharpe</div>
              <div className="text-xl font-bold">
                {result.sharpe_ratio.toFixed(2)}
              </div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400">Max Drawdown</div>
              <div className="text-xl font-bold">
                {result.max_drawdown_pct.toFixed(2)}%
              </div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400">Win Rate</div>
              <div className="text-xl font-bold">
                {result.win_rate.toFixed(1)}%
              </div>
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 space-y-2">
            <div className="text-sm text-gray-400">
              Trades: {result.total_trades} | Final Capital:{' '}
              {result.final_capital.toLocaleString()}
            </div>
            {result.chart_image ? (
              <img
                src={`data:image/png;base64,${result.chart_image}`}
                alt="Backtest chart"
                className="w-full rounded"
              />
            ) : (
              <div className="text-gray-500 text-sm">
                Chart image not available.
              </div>
            )}
          </div>
        </div>
      )}

      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h2 className="text-lg font-medium mb-3">Recent Runs</h2>
        {historyError ? (
          <ErrorMessage
            message={
              historyErrorData instanceof Error
                ? historyErrorData.message
                : 'Failed to load backtest history.'
            }
            onRetry={() => refetchHistory()}
          />
        ) : historyLoading ? (
          <TableSkeleton rows={5} columns={6} />
        ) : history?.runs?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-gray-400">
                <tr>
                  <th className="text-left py-2">Run</th>
                  <th className="text-left py-2">Asset</th>
                  <th className="text-left py-2">Strategy</th>
                  <th className="text-left py-2">Symbol</th>
                  <th className="text-right py-2">Return</th>
                  <th className="text-right py-2">Trades</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {history.runs.map((run) => (
                  <tr key={run.run_id}>
                    <td className="py-2 text-gray-400">{run.run_id}</td>
                    <td className="py-2">{run.asset_class}</td>
                    <td className="py-2">{run.strategy}</td>
                    <td className="py-2">{run.symbol}</td>
                    <td className="py-2 text-right">
                      {run.total_return_pct.toFixed(2)}%
                    </td>
                    <td className="py-2 text-right">{run.total_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-500">No runs yet.</div>
        )}
      </div>
    </div>
  );
}

export default Backtest;
