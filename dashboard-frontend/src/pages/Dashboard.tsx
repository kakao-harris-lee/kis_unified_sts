import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { tradingApi } from '../api/client';
import StatusCard from '../components/StatusCard';
import StatCard from '../components/StatCard';
import ErrorMessage from '../components/ErrorMessage';
import RefreshIndicator from '../components/RefreshIndicator';
import ConfirmationModal from '../components/ConfirmationModal';
import VenueMetrics from '../components/VenueMetrics';
import useQueryWithError from '../hooks/useQueryWithError';

interface TradingStatus {
  is_running: boolean;
  market_status: string;
  active_strategies: string[];
  total_positions: number;
  total_pnl: number;
  unrealized_pnl: number;
  closed_trades: number;
  closed_pnl: number;
  closed_win_rate: number;
  last_update: string;
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
            title="Market Regime"
            value={status?.market_status || 'Unknown'}
            status={status?.market_status?.includes('BULL') ? 'success' : status?.market_status?.includes('BEAR') ? 'warning' : 'neutral'}
            loading={statusLoading}
          />
          <StatusCard
            title="Open Positions"
            value={String(status?.total_positions ?? 0)}
            loading={statusLoading}
          />
          <StatusCard
            title="Active Strategies"
            value={`${status?.active_strategies?.length || 0} (${status?.active_strategies?.join(', ') || '-'})`}
            loading={statusLoading}
          />
        </div>
      </div>

      {/* Session Performance */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Session Performance</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Unrealized P&L"
            value={`${(status?.unrealized_pnl ?? 0) >= 0 ? '+' : ''}${Math.round(status?.unrealized_pnl ?? 0).toLocaleString()}`}
            loading={statusLoading}
            variant={(status?.unrealized_pnl ?? 0) > 0 ? 'positive' : (status?.unrealized_pnl ?? 0) < 0 ? 'negative' : 'neutral'}
          />
          <StatCard
            title="Realized P&L"
            value={`${(status?.closed_pnl ?? 0) >= 0 ? '+' : ''}${Math.round(status?.closed_pnl ?? 0).toLocaleString()}`}
            loading={statusLoading}
            variant={(status?.closed_pnl ?? 0) > 0 ? 'positive' : (status?.closed_pnl ?? 0) < 0 ? 'negative' : 'neutral'}
          />
          <StatCard
            title="Closed Trades"
            value={status?.closed_trades ?? 0}
            loading={statusLoading}
          />
          <StatCard
            title="Win Rate (Closed)"
            value={`${(status?.closed_win_rate ?? 0).toFixed(1)}%`}
            loading={statusLoading}
            variant={(status?.closed_win_rate ?? 0) > 50 ? 'positive' : (status?.closed_win_rate ?? 0) > 0 ? 'negative' : 'neutral'}
          />
        </div>
      </div>

      {/* Venue Metrics Section */}
      <VenueMetrics />

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
