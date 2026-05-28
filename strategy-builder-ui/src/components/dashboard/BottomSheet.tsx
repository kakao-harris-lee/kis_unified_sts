import { type ReactNode } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
}

export default function BottomSheet({ open, onClose, title, children }: Props) {
  if (!open) return null
  return (
    <>
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        className="fixed bottom-0 left-0 right-0 bg-white rounded-t-xl z-50 p-4 max-h-[80vh] overflow-y-auto"
      >
        {title && <div className="text-sm font-semibold mb-3 text-slate-800">{title}</div>}
        {children}
        <button
          onClick={onClose}
          className="w-full mt-3 py-2 bg-slate-200 text-slate-800 rounded text-sm"
        >
          닫기
        </button>
      </div>
    </>
  )
}
