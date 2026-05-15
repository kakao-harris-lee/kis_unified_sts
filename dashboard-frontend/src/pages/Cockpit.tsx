import { useQuery } from '@tanstack/react-query'
import HeaderBar from '../components/HeaderBar'
import PositionsTableLarge from '../components/PositionsTableLarge'
import SignalsListCompact from '../components/SignalsListCompact'
import FillsListCompact from '../components/FillsListCompact'
import QuickActions from '../components/QuickActions'
import MobileKillSwitchBar from '../components/MobileKillSwitchBar'
import EquityCashCard from '../components/EquityCashCard'
import { useAssetClass } from '../contexts/AssetClassContext'
import { healthApi } from '../api/client'

interface HealthSummary {
  today_pnl: number
}

export default function CockpitPage() {
  const { selectedAsset } = useAssetClass()
  const { data: summary } = useQuery<HealthSummary>({
    queryKey: ['health-summary', selectedAsset],
    queryFn: () => healthApi.getSummary({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: 5000,
  })

  return (
    <>
      <HeaderBar />
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 lg:px-6 pt-2 pb-24 lg:pb-2">
        <div className="lg:hidden mb-2 bg-white rounded shadow-sm p-3">
          <div className="text-[10px] text-slate-500 uppercase">Today P&amp;L</div>
          <div
            className={`text-2xl font-bold ${
              (summary?.today_pnl ?? 0) >= 0 ? 'text-emerald-700' : 'text-rose-700'
            }`}
          >
            ₩{(summary?.today_pnl ?? 0).toLocaleString()}
          </div>
        </div>

        <div className="lg:grid lg:grid-cols-3 lg:gap-2 flex flex-col gap-2">
          <div className="lg:col-span-2">
            <PositionsTableLarge />
          </div>
          <div className="flex flex-col gap-2">
            <EquityCashCard />
            <SignalsListCompact />
            <FillsListCompact />
          </div>
        </div>

        <div className="mt-2">
          <QuickActions />
        </div>
      </div>
      <MobileKillSwitchBar />
    </>
  )
}
