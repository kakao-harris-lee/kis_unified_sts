"use client";

import { useQuery } from '@tanstack/react-query'
import HeaderBar from '@/components/dashboard/HeaderBar'
import PositionsTableLarge from '@/components/dashboard/PositionsTableLarge'
import SignalsListCompact from '@/components/dashboard/SignalsListCompact'
import FillsListCompact from '@/components/dashboard/FillsListCompact'
import QuickActions from '@/components/dashboard/QuickActions'
import MobileKillSwitchBar from '@/components/dashboard/MobileKillSwitchBar'
import EquityCashCard from '@/components/dashboard/EquityCashCard'
import { useAssetClass } from '@/contexts/dashboard/AssetClassContext'
import { healthApi } from '@/lib/dashboard/api'
import { QUERY_INTERVALS_MS } from '@/lib/dashboard/queryIntervals'

interface HealthSummary {
  today_pnl: number
}

export default function CockpitPage() {
  const { selectedAsset } = useAssetClass()
  const { data: summary } = useQuery<HealthSummary>({
    queryKey: ['health-summary', selectedAsset],
    queryFn: () => healthApi.getSummary({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
  })

  return (
    <>
      <HeaderBar />
      <div className="max-w-[1400px] mx-auto px-2 sm:px-4 lg:px-6 pt-2 pb-24 lg:pb-2 text-slate-900">
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
