import { useQuery } from '@tanstack/react-query'
import { useAssetClass } from '@/contexts/dashboard/AssetClassContext'
import { tradingApi } from '@/lib/dashboard/api'
import SideBadge from './SideBadge'
import PositionCard from './PositionCard'
import TableSkeleton from './TableSkeleton'
import ErrorMessage from './ErrorMessage'

interface Position {
  asset_class: 'stock' | 'futures'
  code: string
  name: string
  side: 'BUY' | 'SELL'
  quantity: number
  entry_price: number
  current_price: number
  unrealized_pnl: number
  pnl_pct: number
  strategy: string
  entry_time: string
}

export default function PositionsTableLarge() {
  const { selectedAsset } = useAssetClass()
  const { data, isLoading, error } = useQuery<Position[]>({
    queryKey: ['positions', selectedAsset],
    queryFn: () =>
      tradingApi.getPositions({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: 15000,
  })

  if (isLoading) return <TableSkeleton rows={3} />
  if (error) return <ErrorMessage message="포지션 로드 실패" />
  if (!data || data.length === 0)
    return <div className="text-sm text-slate-500 p-3">오픈 포지션 없음</div>

  return (
    <div>
      <div className="hidden sm:block bg-white text-slate-900 rounded shadow-sm overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-2 py-1 text-left">Side</th>
              <th className="px-2 py-1 text-left">Code</th>
              <th className="px-2 py-1 text-left">Name</th>
              <th className="px-2 py-1 text-right">Qty</th>
              <th className="px-2 py-1 text-right">Entry</th>
              <th className="px-2 py-1 text-right">PnL</th>
              <th className="px-2 py-1 text-left">Strategy</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={`${p.asset_class}-${p.code}`} className="border-t border-slate-100">
                <td className="px-2 py-1"><SideBadge side={p.side} /></td>
                <td className="px-2 py-1 font-mono text-slate-900">{p.code}</td>
                <td className="px-2 py-1 text-slate-900">{p.name}</td>
                <td className="px-2 py-1 text-right">{p.quantity}</td>
                <td className="px-2 py-1 text-right">{p.entry_price.toLocaleString()}</td>
                <td className={`px-2 py-1 text-right ${p.unrealized_pnl >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                  {p.unrealized_pnl >= 0 ? '+' : ''}₩{p.unrealized_pnl.toLocaleString()} ({p.pnl_pct.toFixed(2)}%)
                </td>
                <td className="px-2 py-1 text-slate-500">{p.strategy}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="sm:hidden">
        {data.map((p) => (
          <PositionCard key={`${p.asset_class}-${p.code}`} position={p} />
        ))}
      </div>
    </div>
  )
}
