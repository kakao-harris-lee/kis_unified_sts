import { useQuery } from '@tanstack/react-query'
import { useAssetClass } from '@/contexts/dashboard/AssetClassContext'
import { fillsApi } from '@/lib/dashboard/api'
import { QUERY_INTERVALS_MS } from '@/lib/dashboard/queryIntervals'
import SymbolLabel from './SymbolLabel'

interface Fill {
  signal_id: string
  asset_class: 'stock' | 'futures'
  symbol: string
  code?: string
  name?: string
  side: 'BUY' | 'SELL'
  filled_price: number
  quantity: number
  filled_at: string
  trade_role: 'entry' | 'exit'
  // Execution quality (TCA). null on legacy fills without a requested price.
  slippage_bps?: number | null
}

const MAX_ITEMS = 5

export default function FillsListCompact() {
  const { selectedAsset } = useAssetClass()
  const { data } = useQuery<{ fills: Fill[] }>({
    queryKey: ['fills', selectedAsset, 'compact'],
    queryFn: () =>
      fillsApi.getRecent({ asset_class: selectedAsset, limit: MAX_ITEMS }).then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
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
        <div key={f.signal_id + f.filled_at} className="text-xs flex items-center justify-between gap-2 py-1 border-b last:border-0">
          <div className="flex min-w-0 items-center gap-1">
            {selectedAsset === 'all' && (
              <span className="text-[9px] text-slate-400">
                [{f.asset_class === 'futures' ? '선' : '주'}]
              </span>
            )}
            <span className="text-slate-500">
              {new Date(f.filled_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
            </span>
            <span className={f.side === 'BUY' ? 'text-emerald-700' : 'text-rose-700'}>{f.side}</span>
            <SymbolLabel
              code={f.symbol}
              name={f.name}
              className="min-w-0 truncate"
              nameClassName="text-slate-800"
            />
          </div>
          <span className="shrink-0 text-slate-500">
            {f.filled_price.toLocaleString()} × {f.quantity}
            {f.slippage_bps != null && (
              <span
                className={`ml-1 ${f.slippage_bps > 0 ? 'text-rose-600' : 'text-emerald-600'}`}
                title="체결 슬리피지 (요청가 대비 bps · 양수=불리)"
              >
                {f.slippage_bps > 0 ? '+' : ''}
                {f.slippage_bps.toFixed(0)}bp
              </span>
            )}
          </span>
        </div>
      ))}
      {(!data || data.fills.length === 0) && (
        <div className="text-xs text-slate-400 p-2 text-center">체결 없음</div>
      )}
    </div>
  )
}
