import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import StatCard from './StatCard';
import ErrorMessage from './ErrorMessage';
import RefreshIndicator from './RefreshIndicator';
import useQueryWithError from '../hooks/useQueryWithError';
import { apiClient } from '../api/client';
import type { VenueMetricsData } from '../types';

const COLORS = {
  KRX: '#6c8aff',
  ATS: '#22c55e',
};

function VenueMetrics() {
  const {
    data: metrics,
    isLoading,
    errorMessage,
    refetch,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<VenueMetricsData>({
    queryKey: ['venue-metrics'],
    queryFn: () => apiClient.get('/api/metrics/venue').then((r) => r.data),
    refetchInterval: 15000, // Auto-refresh every 15 seconds
  });

  // Prepare chart data
  const chartData = [
    { name: 'KRX', value: metrics?.krx_count || 0 },
    { name: 'ATS', value: metrics?.ats_count || 0 },
  ];

  const totalOrders = (metrics?.krx_count || 0) + (metrics?.ats_count || 0);
  const atsPercentage = totalOrders > 0
    ? ((metrics?.ats_count || 0) / totalOrders * 100).toFixed(1)
    : '0.0';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Venue Metrics</h2>
        <RefreshIndicator
          lastUpdated={dataUpdatedAt}
          isRefreshing={isFetching}
        />
      </div>

      {errorMessage && (
        <ErrorMessage
          message={errorMessage}
          onRetry={() => refetch()}
        />
      )}

      {/* Distribution Chart */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-medium mb-4">Order Distribution</h3>

        {isLoading ? (
          <div className="h-64 flex items-center justify-center">
            <div className="animate-pulse text-gray-400">Loading chart...</div>
          </div>
        ) : totalOrders === 0 ? (
          <div className="h-64 flex items-center justify-center">
            <div className="text-gray-400">No order data available</div>
          </div>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {chartData.map((entry) => (
                    <Cell key={`cell-${entry.name}`} fill={COLORS[entry.name as keyof typeof COLORS]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a1d28',
                    border: '1px solid #2a2d3a',
                    borderRadius: '8px',
                    color: '#e1e4ed'
                  }}
                  formatter={(value: number) => [`${value} orders`, '']}
                />
                <Legend
                  wrapperStyle={{
                    color: '#e1e4ed',
                    paddingTop: '20px'
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Orders"
          value={totalOrders}
          loading={isLoading}
        />
        <StatCard
          title="ATS Usage"
          value={`${atsPercentage}%`}
          loading={isLoading}
          variant={parseFloat(atsPercentage) > 0 ? 'positive' : 'neutral'}
        />
        <StatCard
          title="ATS Fill Rate"
          value={metrics?.ats_fill_rate != null ? `${(metrics.ats_fill_rate * 100).toFixed(1)}%` : '-'}
          loading={isLoading}
          variant={metrics?.ats_fill_rate && metrics.ats_fill_rate > 0.5 ? 'positive' : 'neutral'}
        />
        <StatCard
          title="ATS Price Improvement"
          value={metrics?.ats_price_improvement_bps != null ? `${metrics.ats_price_improvement_bps.toFixed(1)} bps` : '-'}
          loading={isLoading}
          variant={metrics?.ats_price_improvement_bps && metrics.ats_price_improvement_bps > 0 ? 'positive' : 'neutral'}
        />
      </div>
    </div>
  );
}

export default VenueMetrics;
