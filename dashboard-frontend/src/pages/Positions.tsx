import { useQuery } from '@tanstack/react-query';
import { tradingApi } from '../api/client';
import PositionsTable from '../components/PositionsTable';

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
  const { data: positions, isLoading } = useQuery<Position[]>({
    queryKey: ['positions'],
    queryFn: () => tradingApi.getPositions().then((r) => r.data),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Open Positions</h1>
        <div className="text-sm text-gray-400">
          {positions?.length || 0} position(s)
        </div>
      </div>

      <PositionsTable positions={positions || []} loading={isLoading} />
    </div>
  );
}

export default Positions;
