import { useState } from 'react'
import { tradingApi, killSwitchApi } from '../api/client'
import ConfirmationModal from './ConfirmationModal'

type ConfirmAction = 'kill' | 'stop_futures' | 'stop_stock'

export default function QuickActions() {
  const [confirm, setConfirm] = useState<ConfirmAction | null>(null)

  const handleConfirm = async () => {
    if (confirm === 'kill') await killSwitchApi.trigger()
    if (confirm === 'stop_futures') await tradingApi.stopTrading({ asset_class: 'futures' })
    if (confirm === 'stop_stock') await tradingApi.stopTrading({ asset_class: 'stock' })
    setConfirm(null)
  }

  const title =
    confirm === 'kill'
      ? 'KILL SWITCH 활성화'
      : confirm === 'stop_futures'
        ? '선물 거래 중지'
        : confirm === 'stop_stock'
          ? '주식 거래 중지'
          : ''
  const message =
    confirm === 'kill'
      ? '모든 거래가 즉시 중단됩니다. 계속하시겠습니까?'
      : '해당 자산군 거래를 중지하시겠습니까?'

  return (
    <div className="hidden lg:flex gap-2 p-2 bg-slate-50 rounded">
      <button
        onClick={() => setConfirm('kill')}
        className="px-4 py-2 bg-rose-700 text-white rounded text-sm font-medium hover:bg-rose-800 transition-colors"
      >
        KILL SWITCH
      </button>
      <button
        onClick={() => setConfirm('stop_futures')}
        className="px-4 py-2 bg-slate-600 text-white rounded text-sm font-medium hover:bg-slate-700 transition-colors"
      >
        STOP 선물
      </button>
      <button
        onClick={() => setConfirm('stop_stock')}
        className="px-4 py-2 bg-slate-600 text-white rounded text-sm font-medium hover:bg-slate-700 transition-colors"
      >
        STOP 주식
      </button>
      <ConfirmationModal
        isOpen={confirm !== null}
        onClose={() => setConfirm(null)}
        onConfirm={handleConfirm}
        title={title}
        message={message}
        confirmText={confirm === 'kill' ? 'KILL SWITCH' : '거래 중지'}
        confirmStyle="red"
      />
    </div>
  )
}
