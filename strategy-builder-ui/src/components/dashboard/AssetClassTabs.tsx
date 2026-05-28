import { useAssetClass, type AssetClass } from '@/contexts/dashboard/AssetClassContext'

const TABS: { value: AssetClass; label: string }[] = [
  { value: 'futures', label: '선물' },
  { value: 'all', label: '통합' },
  { value: 'stock', label: '주식' },
]

export default function AssetClassTabs() {
  const { selectedAsset, setSelectedAsset } = useAssetClass()
  return (
    <div role="tablist" aria-label="자산군 선택" className="flex gap-1 bg-slate-800 rounded p-0.5">
      {TABS.map((t) => (
        <button
          key={t.value}
          role="tab"
          aria-selected={selectedAsset === t.value}
          onClick={() => setSelectedAsset(t.value)}
          className={`flex-1 px-3 py-1 rounded text-xs font-medium transition-colors ${
            selectedAsset === t.value
              ? 'bg-blue-600 text-white'
              : 'text-slate-300 hover:bg-slate-700'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
