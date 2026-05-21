import { useQuery } from '@tanstack/react-query'
import { useAssetClass } from '../contexts/AssetClassContext'
import { signalsApi } from '../api/client'

interface Signal {
  id: string
  asset_class: 'stock' | 'futures'
  strategy: string
  symbol: string
  side: 'BUY' | 'SELL'
  confidence?: number
  strength?: number
  price: number
  timestamp: string
  executed: boolean
  setup_type?: string
}

const MAX_ITEMS = 5

export default function SignalsListCompact() {
  const { selectedAsset } = useAssetClass()
  const { data } = useQuery<{ signals: Signal[]; total: number }>({
    queryKey: ['signals', selectedAsset, 'compact'],
    queryFn: () =>
      signalsApi.getSignals({ asset_class: selectedAsset, limit: MAX_ITEMS }).then((r) => r.data),
    refetchInterval: 15000,
  })

  return (
    <div className="bg-white rounded shadow-sm p-2">
      <div className="text-xs font-semibold mb-1 text-slate-600 flex justify-between">
        <span>Recent Signals</span>
        <span className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded-full text-[10px]">
          {data?.total ?? 0}
        </span>
      </div>
      {(data?.signals ?? []).slice(0, MAX_ITEMS).map((s) => {
        const strength = s.strength ?? s.confidence ?? 0
        return (
          <div key={s.id} className="text-xs flex items-center justify-between py-1 border-b last:border-0">
            <div className="flex items-center gap-1">
              {selectedAsset === 'all' && (
                <span className="text-[9px] text-slate-400">
                  [{s.asset_class === 'futures' ? '선' : '주'}]
                </span>
              )}
              <span className="text-slate-500">
                {new Date(s.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
              </span>
              <span className="font-medium text-slate-800">
                {s.setup_type ? `Setup ${s.setup_type}` : s.strategy}
              </span>
              <span className={s.side === 'BUY' ? 'text-emerald-700' : 'text-rose-700'}>
                {s.side === 'BUY' ? 'LONG' : 'SHORT'}
              </span>
            </div>
            <span className="text-slate-500">conf {strength.toFixed(2)}</span>
          </div>
        )
      })}
      {(!data || data.signals.length === 0) && (
        <div className="text-xs text-slate-400 p-2 text-center">시그널 없음</div>
      )}
    </div>
  )
}
