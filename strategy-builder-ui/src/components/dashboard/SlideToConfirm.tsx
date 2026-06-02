import { useCallback, useRef, useState } from 'react'

interface Props {
  label: string
  onConfirm: () => void
}

const COMMIT_THRESHOLD = 0.9

export default function SlideToConfirm({ label, onConfirm }: Props) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [progress, setProgress] = useState(0)
  const [dragging, setDragging] = useState(false)
  const startX = useRef(0)
  // State, not a ref: trackWidth is read during render (the knob transform), so
  // it must be reactive — reading a ref during render is unsupported.
  const [trackWidth, setTrackWidth] = useState(0)

  const reset = useCallback(() => setProgress(0), [])

  const onPointerDown = (e: React.PointerEvent) => {
    if (!trackRef.current) return
    trackRef.current.setPointerCapture(e.pointerId)
    startX.current = e.clientX
    setTrackWidth(trackRef.current.getBoundingClientRect().width)
    setDragging(true)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging) return
    const dx = e.clientX - startX.current
    const ratio = Math.max(0, Math.min(1, dx / (trackWidth - 56)))
    setProgress(ratio)
    if (ratio >= COMMIT_THRESHOLD) {
      setDragging(false)
      onConfirm()
      setTimeout(reset, 500)
    }
  }

  const onPointerUp = () => {
    if (progress < COMMIT_THRESHOLD) reset()
    setDragging(false)
  }

  const enterDownTime = useRef(0)
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && enterDownTime.current === 0) {
      enterDownTime.current = Date.now()
    }
  }
  const onKeyUp = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      const held = Date.now() - enterDownTime.current
      enterDownTime.current = 0
      if (held >= 3000) onConfirm()
    }
  }

  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  if (reducedMotion) {
    return (
      <button
        onClick={onConfirm}
        className="w-full h-14 bg-rose-700 text-white font-semibold rounded"
        aria-label={label}
      >
        {label} (2-tap)
      </button>
    )
  }

  return (
    <div
      ref={trackRef}
      role="slider"
      aria-label={label}
      aria-valuenow={Math.round(progress * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onKeyDown={onKeyDown}
      onKeyUp={onKeyUp}
      className="relative w-full h-14 bg-slate-300 rounded overflow-hidden select-none touch-none"
      style={{
        backgroundColor: `rgb(${203 - progress * 130}, ${213 - progress * 175}, ${225 - progress * 215})`,
      }}
    >
      <div
        className="absolute top-0 left-0 h-full w-14 bg-rose-700 rounded shadow"
        style={{
          transform: `translateX(${progress * (trackWidth - 56)}px)`,
          transition: dragging ? 'none' : 'transform 200ms',
        }}
      />
      <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold pointer-events-none">
        → {label}
      </span>
    </div>
  )
}
