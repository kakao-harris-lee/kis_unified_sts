import { tradingApi } from '../api/client';
import PositionsTable from '../components/PositionsTable';
import ErrorMessage from '../components/ErrorMessage';
import RefreshIndicator from '../components/RefreshIndicator';
import useQueryWithError from '../hooks/useQueryWithError';

export interface Position {
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  strategy: string;
  entry_time: string;
}

function Positions() {
  const {
    data: positions,
    isLoading,
    errorMessage,
    refetch,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<Position[]>({
    queryKey: ['positions'],
    queryFn: () => tradingApi.getPositions().then((r) => r.data),
    refetchInterval: 5000, // Auto-refresh every 5 seconds
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold">Open Positions</h1>
          <div className="text-sm text-gray-400">
            {positions?.length || 0} position(s)
          </div>
        </div>
        <RefreshIndicator
          lastUpdated={dataUpdatedAt}
          isRefreshing={isFetching}
        />
      </div>

      {errorMessage && (
        <ErrorMessage message={errorMessage} onRetry={() => refetch()} />
      )}

      <PositionsTable positions={positions || []} loading={isLoading} />
    </div>
  );
}

export default Positions;
