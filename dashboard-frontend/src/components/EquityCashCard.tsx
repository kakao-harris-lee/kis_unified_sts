import { useQuery } from '@tanstack/react-query'
import { tradingApi } from '../api/client'
import { useAssetClass } from '../contexts/AssetClassContext'

interface AccountSummary {
  initial_balance: number
  balance: number
  equity: number
  realized_pnl: number
  unrealized_pnl: number
  open_positions: number
}

interface TradingStatusResponse {
  is_running: boolean
  account: AccountSummary | null
}

function pnlColor(value: number): string {
  if (value > 0) return 'text-emerald-700'
  if (value < 0) return 'text-rose-700'
  return 'text-slate-700'
}

function formatKRW(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}₩${Math.round(value).toLocaleString()}`
}

export default function EquityCashCard() {
  const { selectedAsset } = useAssetClass()
  const { data, isLoading } = useQuery<TradingStatusResponse>({
    queryKey: ['trading-status-account', selectedAsset],
    queryFn: () =>
      tradingApi.getStatus({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: 5000,
  })

  if (isLoading) {
    return (
      <div
        className="bg-white rounded shadow-sm p-3"
        data-testid="equity-card-loading"
      >
        <div className="h-3 w-16 bg-slate-200 rounded animate-pulse mb-2" />
        <div className="h-6 w-32 bg-slate-200 rounded animate-pulse" />
      </div>
    )
  }

  // Paper engine 미가동 — KIS 모의서버는 선물 잔고조회 미지원이라 표시 불가
  const account = data?.account
  if (!account) {
    return null
  }

  return (
    <div
      className="bg-white rounded shadow-sm p-3"
      data-testid="equity-cash-card"
      aria-label="Equity and cash summary"
    >
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-[10px] text-slate-500 uppercase tracking-wide">
          Equity · Cash
        </span>
        <span className="text-[10px] text-slate-400">paper</span>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-slate-500">Equity</span>
          <span className="text-xl font-bold text-slate-900">
            ₩{Math.round(account.equity).toLocaleString()}
          </span>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-slate-500">Cash</span>
          <span className="text-sm font-semibold text-slate-700">
            ₩{Math.round(account.balance).toLocaleString()}
          </span>
        </div>
        <div className="flex items-baseline justify-between pt-1.5 border-t border-slate-100">
          <span className="text-xs text-slate-500">Realized P&amp;L</span>
          <span className={`text-sm font-semibold ${pnlColor(account.realized_pnl)}`}>
            {formatKRW(account.realized_pnl)}
          </span>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-slate-500">Unrealized</span>
          <span className={`text-sm font-semibold ${pnlColor(account.unrealized_pnl)}`}>
            {formatKRW(account.unrealized_pnl)}
          </span>
        </div>
        <div className="flex items-baseline justify-between text-[10px] text-slate-400 pt-1">
          <span>Open positions</span>
          <span>{account.open_positions}</span>
        </div>
      </div>
    </div>
  )
}
