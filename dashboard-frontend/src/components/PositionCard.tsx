import SideBadge from './SideBadge'

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

export default function PositionCard({ position: p }: { position: Position }) {
  const positive = p.unrealized_pnl >= 0
  return (
    <div className="border border-slate-200 rounded-lg p-3 mb-2 bg-white text-slate-900 shadow-sm">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <SideBadge side={p.side} />
          <span className="font-semibold text-sm text-slate-900">{p.code} {p.name}</span>
        </div>
        <span className={`text-xs font-medium ${positive ? 'text-emerald-700' : 'text-rose-700'}`}>
          {positive ? '+' : ''}{p.pnl_pct.toFixed(2)}%
        </span>
      </div>
      <div className="text-xs text-slate-600 flex justify-between">
        <span>{p.quantity}@{p.entry_price.toLocaleString()}</span>
        <span className={positive ? 'text-emerald-700' : 'text-rose-700'}>
          {positive ? '+' : ''}₩{p.unrealized_pnl.toLocaleString()}
        </span>
      </div>
      <div className="text-[10px] text-slate-400 mt-1">{p.strategy}</div>
    </div>
  )
}
