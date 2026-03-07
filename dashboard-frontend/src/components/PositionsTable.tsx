import { Position } from '../pages/Positions';
import TableSkeleton from './TableSkeleton';

interface PositionsTableProps {
  positions: Position[];
  loading?: boolean;
  error?: string | null;
}

function PositionsTable({ positions, loading, error }: PositionsTableProps) {
  if (error) {
    return (
      <div className="bg-gray-800 rounded-lg p-8 text-center border border-red-800">
        <div className="text-red-400">{error}</div>
      </div>
    );
  }

  if (loading) {
    return <TableSkeleton rows={5} columns={8} />;
  }

  if (positions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-400">
        No open positions
      </div>
    );
  }

  return (
    <>
      {/* Mobile Card View */}
      <div className="block md:hidden space-y-4">
        {positions.map((position, idx) => (
          <div
            key={idx}
            className="bg-gray-800 rounded-lg p-4 border border-gray-700"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="font-medium text-lg">{position.symbol}</span>
              <span
                className={`px-2 py-1 rounded text-xs font-medium ${
                  position.side === 'BUY'
                    ? 'bg-green-900 text-green-300'
                    : 'bg-red-900 text-red-300'
                }`}
              >
                {position.side}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-gray-400">Quantity</div>
                <div className="font-medium">{position.quantity}</div>
              </div>
              <div>
                <div className="text-gray-400">Entry Price</div>
                <div className="font-medium">
                  {position.entry_price.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-gray-400">Current Price</div>
                <div className="font-medium">
                  {position.current_price.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-gray-400">P&L</div>
                <div
                  className={`font-medium ${
                    position.unrealized_pnl >= 0
                      ? 'text-green-400'
                      : 'text-red-400'
                  }`}
                >
                  {position.unrealized_pnl >= 0 ? '+' : ''}
                  {position.unrealized_pnl.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-gray-400">P&L %</div>
                <div
                  className={`font-medium ${
                    position.unrealized_pnl_pct >= 0
                      ? 'text-green-400'
                      : 'text-red-400'
                  }`}
                >
                  {position.unrealized_pnl_pct >= 0 ? '+' : ''}
                  {position.unrealized_pnl_pct.toFixed(2)}%
                </div>
              </div>
              <div>
                <div className="text-gray-400">Strategy</div>
                <div className="font-medium text-gray-300">
                  {position.strategy}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop Table View with Horizontal Scroll */}
      <div className="hidden md:block bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                  Symbol
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                  Side
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                  Quantity
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                  Entry Price
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                  Current Price
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                  P&L
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                  P&L %
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                  Strategy
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {positions.map((position, idx) => (
                <tr key={idx} className="hover:bg-gray-750">
                  <td className="px-4 py-3 font-medium">{position.symbol}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        position.side === 'BUY'
                          ? 'bg-green-900 text-green-300'
                          : 'bg-red-900 text-red-300'
                      }`}
                    >
                      {position.side}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">{position.quantity}</td>
                  <td className="px-4 py-3 text-right">
                    {position.entry_price.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {position.current_price.toLocaleString()}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-medium ${
                      position.unrealized_pnl >= 0
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}
                  >
                    {position.unrealized_pnl >= 0 ? '+' : ''}
                    {position.unrealized_pnl.toLocaleString()}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-medium ${
                      position.unrealized_pnl_pct >= 0
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}
                  >
                    {position.unrealized_pnl_pct >= 0 ? '+' : ''}
                    {position.unrealized_pnl_pct.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400">
                    {position.strategy}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

export default PositionsTable;
