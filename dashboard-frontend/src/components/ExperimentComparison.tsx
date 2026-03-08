import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface ExperimentRun {
  run_id: string;
  experiment_id: string;
  status: string;
  start_time: number;
  end_time?: number;
  metrics: Record<string, number>;
  params: Record<string, string>;
  tags: Record<string, string>;
}

interface ExperimentComparisonProps {
  runs: ExperimentRun[];
  isLoading?: boolean;
}

type SortColumn = 'run_id' | 'status' | 'start_time' | 'sharpe_ratio' | 'total_return_pct' | 'win_rate' | 'max_drawdown_pct';
type SortDirection = 'asc' | 'desc';

function ExperimentComparison({ runs, isLoading }: ExperimentComparisonProps) {
  const [sortColumn, setSortColumn] = useState<SortColumn>('start_time');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  const sortedRuns = [...runs].sort((a, b) => {
    let aValue: string | number;
    let bValue: string | number;

    if (sortColumn === 'run_id') {
      aValue = a.run_id;
      bValue = b.run_id;
    } else if (sortColumn === 'status') {
      aValue = a.status;
      bValue = b.status;
    } else if (sortColumn === 'start_time') {
      aValue = a.start_time;
      bValue = b.start_time;
    } else {
      aValue = a.metrics[sortColumn] ?? 0;
      bValue = b.metrics[sortColumn] ?? 0;
    }

    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortDirection === 'asc'
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue);
    }

    return sortDirection === 'asc'
      ? (aValue as number) - (bValue as number)
      : (bValue as number) - (aValue as number);
  });

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatMetricValue = (value: number | undefined) => {
    return typeof value === 'number' ? value.toFixed(4) : '-';
  };

  const SortIcon = ({ column }: { column: SortColumn }) => {
    if (sortColumn !== column) {
      return (
        <svg className="w-4 h-4 inline ml-1 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      );
    }
    return sortDirection === 'asc' ? (
      <svg className="w-4 h-4 inline ml-1 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
      </svg>
    ) : (
      <svg className="w-4 h-4 inline ml-1 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    );
  };

  const chartData = runs.map((run) => ({
    name: run.run_id.slice(0, 8),
    sharpe: run.metrics.sharpe_ratio ?? 0,
    return: run.metrics.total_return_pct ?? 0,
    winRate: run.metrics.win_rate ?? 0,
    drawdown: run.metrics.max_drawdown_pct ?? 0,
  }));

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-700 rounded w-1/4" />
            <div className="h-64 bg-gray-700 rounded" />
          </div>
        </div>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="text-center text-gray-400 py-8">
          No runs to compare
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Metrics Comparison Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Sharpe Ratio Comparison</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
              />
              <Bar dataKey="sharpe" fill="#10B981" name="Sharpe Ratio" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Total Return % Comparison</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
              />
              <Bar dataKey="return" fill="#3B82F6" name="Return %" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Win Rate Comparison</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
              />
              <Bar dataKey="winRate" fill="#8B5CF6" name="Win Rate" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Max Drawdown % Comparison</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
              />
              <Bar dataKey="drawdown" fill="#EF4444" name="Drawdown %" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-lg font-medium mb-4">Run Comparison Table</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-gray-400 border-b border-gray-700">
              <tr>
                <th
                  className="text-left py-2 px-3 cursor-pointer hover:text-gray-200"
                  onClick={() => handleSort('run_id')}
                >
                  Run ID <SortIcon column="run_id" />
                </th>
                <th
                  className="text-left py-2 px-3 cursor-pointer hover:text-gray-200"
                  onClick={() => handleSort('status')}
                >
                  Status <SortIcon column="status" />
                </th>
                <th
                  className="text-left py-2 px-3 cursor-pointer hover:text-gray-200"
                  onClick={() => handleSort('start_time')}
                >
                  Start Time <SortIcon column="start_time" />
                </th>
                <th
                  className="text-right py-2 px-3 cursor-pointer hover:text-gray-200"
                  onClick={() => handleSort('sharpe_ratio')}
                >
                  Sharpe <SortIcon column="sharpe_ratio" />
                </th>
                <th
                  className="text-right py-2 px-3 cursor-pointer hover:text-gray-200"
                  onClick={() => handleSort('total_return_pct')}
                >
                  Return % <SortIcon column="total_return_pct" />
                </th>
                <th
                  className="text-right py-2 px-3 cursor-pointer hover:text-gray-200"
                  onClick={() => handleSort('win_rate')}
                >
                  Win Rate <SortIcon column="win_rate" />
                </th>
                <th
                  className="text-right py-2 px-3 cursor-pointer hover:text-gray-200"
                  onClick={() => handleSort('max_drawdown_pct')}
                >
                  Drawdown % <SortIcon column="max_drawdown_pct" />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {sortedRuns.map((run) => (
                <tr key={run.run_id} className="hover:bg-gray-900/50">
                  <td className="py-2 px-3 font-mono text-xs" title={run.run_id}>
                    {run.run_id.slice(0, 8)}...
                  </td>
                  <td className="py-2 px-3">
                    <span
                      className={`px-2 py-1 rounded text-xs ${
                        run.status === 'FINISHED'
                          ? 'bg-green-900/30 text-green-400'
                          : run.status === 'RUNNING'
                          ? 'bg-blue-900/30 text-blue-400'
                          : 'bg-red-900/30 text-red-400'
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-gray-400">
                    {formatTimestamp(run.start_time)}
                  </td>
                  <td className="py-2 px-3 text-right font-mono">
                    {formatMetricValue(run.metrics.sharpe_ratio)}
                  </td>
                  <td className="py-2 px-3 text-right font-mono">
                    {formatMetricValue(run.metrics.total_return_pct)}
                  </td>
                  <td className="py-2 px-3 text-right font-mono">
                    {formatMetricValue(run.metrics.win_rate)}
                  </td>
                  <td className="py-2 px-3 text-right font-mono">
                    {formatMetricValue(run.metrics.max_drawdown_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Total Runs</div>
          <div className="text-2xl font-bold">{runs.length}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Finished</div>
          <div className="text-2xl font-bold text-green-400">
            {runs.filter((r) => r.status === 'FINISHED').length}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Running</div>
          <div className="text-2xl font-bold text-blue-400">
            {runs.filter((r) => r.status === 'RUNNING').length}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Failed</div>
          <div className="text-2xl font-bold text-red-400">
            {runs.filter((r) => r.status === 'FAILED').length}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExperimentComparison;
