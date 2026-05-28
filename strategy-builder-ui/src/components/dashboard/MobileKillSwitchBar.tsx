import { useState } from 'react'
import { killSwitchApi } from '@/lib/dashboard/api'
import SlideToConfirm from './SlideToConfirm'

export default function MobileKillSwitchBar() {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-rose-700 text-white shadow-lg"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {!expanded ? (
        <button
          onClick={() => setExpanded(true)}
          className="w-full h-16 font-semibold text-sm"
        >
          🔴 KILL SWITCH
        </button>
      ) : (
        <div className="p-2">
          <SlideToConfirm
            label="Slide to confirm KILL SWITCH"
            onConfirm={async () => {
              await killSwitchApi.trigger()
              setExpanded(false)
            }}
          />
          <button
            onClick={() => setExpanded(false)}
            className="w-full mt-1 text-xs underline"
          >
            취소
          </button>
        </div>
      )}
    </div>
  )
}
