import { tradingApi } from '../api/client';
import HeaderBar from '../components/HeaderBar';
import PositionCard from '../components/PositionCard';
import PositionsTable from '../components/PositionsTable';
import ErrorMessage from '../components/ErrorMessage';
import RefreshIndicator from '../components/RefreshIndicator';
import useQueryWithError from '../hooks/useQueryWithError';
import { useAssetClass } from '../contexts/AssetClassContext';

export interface Position {
  asset_class?: 'stock' | 'futures';
  code: string;
  name: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_pct: number;
  strategy: string;
  entry_time: string;
}

function Positions() {
  const { selectedAsset } = useAssetClass();

  const {
    data: positions,
    isLoading,
    errorMessage,
    refetch,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<Position[]>({
    queryKey: ['positions', selectedAsset],
    queryFn: () =>
      tradingApi.getPositions({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: 5000, // Auto-refresh every 5 seconds
  });

  return (
    <>
      <HeaderBar />
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 lg:px-6 pt-2 pb-24 lg:pb-2">
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

          {/* Mobile Card View */}
          <div className="sm:hidden">
            {(positions ?? []).map((p) => (
              <PositionCard
                key={`${p.code}-${p.entry_time}`}
                position={{
                  ...p,
                  asset_class: p.asset_class ?? (selectedAsset === 'all' ? 'stock' : selectedAsset),
                }}
              />
            ))}
            {!isLoading && (positions ?? []).length === 0 && (
              <div className="text-center text-sm text-slate-500 py-8">
                No open positions
              </div>
            )}
          </div>

          {/* Desktop Table View */}
          <div className="hidden sm:block">
            <PositionsTable positions={positions || []} loading={isLoading} />
          </div>
        </div>
      </div>
    </>
  );
}

export default Positions;
