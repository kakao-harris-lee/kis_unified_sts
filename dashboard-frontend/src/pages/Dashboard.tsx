import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { tradingApi, tradesApi } from '../api/client';
import StatusCard from '../components/StatusCard';
import StatCard from '../components/StatCard';
import ErrorMessage from '../components/ErrorMessage';
import RefreshIndicator from '../components/RefreshIndicator';
import ConfirmationModal from '../components/ConfirmationModal';
import useQueryWithError from '../hooks/useQueryWithError';

interface TradingStatus {
  is_running: boolean;
  market_status: string;
  active_strategies: string[];
  last_update: string;
}

interface TradeStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  profit_factor: number;
}

function Dashboard() {
  const queryClient = useQueryClient();
  const [isStartModalOpen, setIsStartModalOpen] = useState(false);
  const [isStopModalOpen, setIsStopModalOpen] = useState(false);

  const {
    data: status,
    isLoading: statusLoading,
    errorMessage: statusError,
    refetch: refetchStatus,
    dataUpdatedAt: statusUpdatedAt,
    isFetching: statusFetching,
  } = useQueryWithError<TradingStatus>({
    queryKey: ['trading-status'],
    queryFn: () => tradingApi.getStatus().then((r) => r.data),
    refetchInterval: 10000, // Auto-refresh every 10 seconds
  });

  const {
    data: stats,
    isLoading: statsLoading,
    errorMessage: statsError,
    refetch: refetchStats,
    dataUpdatedAt: statsUpdatedAt,
    isFetching: statsFetching,
  } = useQueryWithError<TradeStats>({
    queryKey: ['trade-stats'],
    queryFn: () => tradesApi.getStatistics().then((r) => r.data),
    refetchInterval: 10000, // Auto-refresh every 10 seconds
  });

  const startTradingMutation = useMutation({
    mutationFn: () => tradingApi.startTrading(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trading-status'] });
    },
  });

  const stopTradingMutation = useMutation({
    mutationFn: () => tradingApi.stopTrading(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trading-status'] });
    },
  });

  const handleStartTrading = () => {
    setIsStartModalOpen(true);
  };

  const handleConfirmStart = () => {
    setIsStartModalOpen(false);
    startTradingMutation.mutate();
  };

  const handleStopTrading = () => {
    setIsStopModalOpen(true);
  };

  const handleConfirmStop = () => {
    setIsStopModalOpen(false);
    stopTradingMutation.mutate();
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <div className="flex space-x-4">
            <button
              onClick={handleStartTrading}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={status?.is_running || startTradingMutation.isPending}
            >
              {startTradingMutation.isPending ? 'Starting...' : 'Start Trading'}
            </button>
            <button
              onClick={handleStopTrading}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={!status?.is_running || stopTradingMutation.isPending}
            >
              {stopTradingMutation.isPending ? 'Stopping...' : 'Stop Trading'}
            </button>
          </div>
        </div>

        {/* Mutation Errors */}
        {startTradingMutation.error && (
          <ErrorMessage
            message={`Failed to start trading: ${startTradingMutation.error instanceof Error ? startTradingMutation.error.message : 'Unknown error'}`}
            onRetry={() => startTradingMutation.reset()}
          />
        )}
        {stopTradingMutation.error && (
          <ErrorMessage
            message={`Failed to stop trading: ${stopTradingMutation.error instanceof Error ? stopTradingMutation.error.message : 'Unknown error'}`}
            onRetry={() => stopTradingMutation.reset()}
          />
        )}
      </div>

      {/* Status Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Trading Status</h2>
          <RefreshIndicator
            lastUpdated={statusUpdatedAt}
            isRefreshing={statusFetching}
          />
        </div>

        {statusError && (
          <ErrorMessage
            message={statusError}
            onRetry={() => refetchStatus()}
          />
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatusCard
            title="Trading Status"
            value={status?.is_running ? 'Running' : 'Stopped'}
            status={status?.is_running ? 'success' : 'warning'}
            loading={statusLoading}
          />
          <StatusCard
            title="Market Status"
            value={status?.market_status || 'Unknown'}
            status={status?.market_status === 'open' ? 'success' : 'neutral'}
            loading={statusLoading}
          />
          <StatusCard
            title="Active Strategies"
            value={String(status?.active_strategies?.length || 0)}
            loading={statusLoading}
          />
          <StatusCard
            title="Last Update"
            value={
              status?.last_update
                ? new Date(status.last_update).toLocaleTimeString()
                : '-'
            }
            loading={statusLoading}
          />
        </div>
      </div>

      {/* Stats Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Performance Statistics</h2>
          <RefreshIndicator
            lastUpdated={statsUpdatedAt}
            isRefreshing={statsFetching}
          />
        </div>

        {statsError && (
          <ErrorMessage
            message={statsError}
            onRetry={() => refetchStats()}
          />
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Trades"
            value={stats?.total_trades || 0}
            loading={statsLoading}
          />
          <StatCard
            title="Win Rate"
            value={`${((stats?.win_rate || 0) * 100).toFixed(1)}%`}
            loading={statsLoading}
            variant={stats?.win_rate && stats.win_rate > 0.5 ? 'positive' : stats?.win_rate ? 'negative' : 'neutral'}
          />
          <StatCard
            title="Total P&L"
            value={`${(stats?.total_pnl || 0).toFixed(2)}%`}
            loading={statsLoading}
            variant={stats?.total_pnl && stats.total_pnl > 0 ? 'positive' : stats?.total_pnl && stats.total_pnl < 0 ? 'negative' : 'neutral'}
          />
          <StatCard
            title="Profit Factor"
            value={(stats?.profit_factor || 0).toFixed(2)}
            loading={statsLoading}
            variant={stats?.profit_factor && stats.profit_factor > 1 ? 'positive' : stats?.profit_factor && stats.profit_factor < 1 ? 'negative' : 'neutral'}
          />
        </div>
      </div>

      {/* Confirmation Modals */}
      <ConfirmationModal
        isOpen={isStartModalOpen}
        onClose={() => setIsStartModalOpen(false)}
        onConfirm={handleConfirmStart}
        title="Start Trading"
        message="Are you sure you want to start trading? This will activate all enabled strategies and begin executing trades."
        confirmText="Start Trading"
        confirmStyle="green"
      />

      <ConfirmationModal
        isOpen={isStopModalOpen}
        onClose={() => setIsStopModalOpen(false)}
        onConfirm={handleConfirmStop}
        title="Stop Trading"
        message="Are you sure you want to stop trading? This will halt all active strategies and may affect open positions."
        confirmText="Stop Trading"
        confirmStyle="red"
      />
    </div>
  );
}

export default Dashboard;
