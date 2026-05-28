import { useQuery } from '@tanstack/react-query'
import { useAssetClass } from '@/contexts/dashboard/AssetClassContext'
import { fillsApi } from '@/lib/dashboard/api'

interface Fill {
  signal_id: string
  asset_class: 'stock' | 'futures'
  symbol: string
  side: 'BUY' | 'SELL'
  filled_price: number
  quantity: number
  filled_at: string
  trade_role: 'entry' | 'exit'
}

const MAX_ITEMS = 5

export default function FillsListCompact() {
  const { selectedAsset } = useAssetClass()
  const { data } = useQuery<{ fills: Fill[] }>({
    queryKey: ['fills', selectedAsset, 'compact'],
    queryFn: () =>
      fillsApi.getRecent({ asset_class: selectedAsset, limit: MAX_ITEMS }).then((r) => r.data),
    refetchInterval: 15000,
  })

  return (
    <div className="bg-white rounded shadow-sm p-2">
      <div className="text-xs font-semibold mb-1 text-slate-600 flex justify-between">
        <span>Recent Fills</span>
        <span className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded-full text-[10px]">
          {data?.fills.length ?? 0}
        </span>
      </div>
      {(data?.fills ?? []).map((f) => (
        <div key={f.signal_id + f.filled_at} className="text-xs flex items-center justify-between py-1 border-b last:border-0">
          <div className="flex items-center gap-1">
            {selectedAsset === 'all' && (
              <span className="text-[9px] text-slate-400">
                [{f.asset_class === 'futures' ? '선' : '주'}]
              </span>
            )}
            <span className="text-slate-500">
              {new Date(f.filled_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
            </span>
            <span className={f.side === 'BUY' ? 'text-emerald-700' : 'text-rose-700'}>{f.side}</span>
            <span className="font-mono">{f.symbol}</span>
          </div>
          <span className="text-slate-500">{f.filled_price.toLocaleString()} × {f.quantity}</span>
        </div>
      ))}
      {(!data || data.fills.length === 0) && (
        <div className="text-xs text-slate-400 p-2 text-center">체결 없음</div>
      )}
    </div>
  )
}
