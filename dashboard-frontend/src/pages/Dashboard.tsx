import { useQuery } from '@tanstack/react-query';
import { tradingApi, tradesApi } from '../api/client';
import StatusCard from '../components/StatusCard';
import StatCard from '../components/StatCard';

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
  const { data: status, isLoading: statusLoading } = useQuery<TradingStatus>({
    queryKey: ['trading-status'],
    queryFn: () => tradingApi.getStatus().then((r) => r.data),
  });

  const { data: stats, isLoading: statsLoading } = useQuery<TradeStats>({
    queryKey: ['trade-stats'],
    queryFn: () => tradesApi.getStatistics().then((r) => r.data),
  });

  const handleStartTrading = async () => {
    await tradingApi.startTrading();
  };

  const handleStopTrading = async () => {
    await tradingApi.stopTrading();
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex space-x-4">
          <button
            onClick={handleStartTrading}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-md"
            disabled={status?.is_running}
          >
            Start Trading
          </button>
          <button
            onClick={handleStopTrading}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-md"
            disabled={!status?.is_running}
          >
            Stop Trading
          </button>
        </div>
      </div>

      {/* Status Section */}
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

      {/* Stats Section */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Performance Statistics</h2>
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
            highlight={stats?.win_rate && stats.win_rate > 0.5}
          />
          <StatCard
            title="Total P&L"
            value={`${(stats?.total_pnl || 0).toFixed(2)}%`}
            loading={statsLoading}
            highlight={stats?.total_pnl && stats.total_pnl > 0}
          />
          <StatCard
            title="Profit Factor"
            value={(stats?.profit_factor || 0).toFixed(2)}
            loading={statsLoading}
            highlight={stats?.profit_factor && stats.profit_factor > 1}
          />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
