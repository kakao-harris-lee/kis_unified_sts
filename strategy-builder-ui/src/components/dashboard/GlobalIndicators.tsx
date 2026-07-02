import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { useAssetClass } from '@/contexts/dashboard/AssetClassContext'
import { healthApi, marketRiskApi } from '@/lib/dashboard/api'
import type { MarketRiskLatest } from '@/lib/dashboard/marketRisk'
import { normalizeBand } from '@/lib/dashboard/marketRisk'
import { BAND_HEADER_CHIP_CLASSES } from '@/components/dashboard/RiskBandBadge'
import { QUERY_INTERVALS_MS } from '@/lib/dashboard/queryIntervals'

interface HealthSummary {
  processes: Array<{ asset_class: string; alive: boolean }>
  data_sources: Array<{ asset_class: string; fresh_ratio: number }>
  kill_switch: { enabled: boolean; active_conditions: { name: string }[] }
  today_pnl: number
}

// Cockpit ops-summary chip for the Market Risk Score (roadmap §6.2). Renders
// nothing while the engine has not published yet (graceful absence).
function MarketRiskChip() {
  const { data } = useQuery<MarketRiskLatest>({
    queryKey: ['market-risk'],
    queryFn: () => marketRiskApi.getLatest().then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
  })

  const risk = data?.risk
  if (!risk || risk.score === null) return null

  const band = normalizeBand(risk.band)
  const chipClass = band ? BAND_HEADER_CHIP_CLASSES[band] : 'bg-slate-700'
  return (
    <Link
      href="/market"
      className={`px-2 py-0.5 rounded ${chipClass}`}
      aria-label={`Market risk score ${risk.score.toFixed(0)}, band ${band ?? 'unknown'}${risk.degraded ? ', degraded' : ''}`}
      title={`Market Risk ${risk.score.toFixed(1)} · ${band ?? '-'} · ${risk.regime ?? '-'}${risk.degraded ? ' · DEGRADED' : ''}`}
    >
      ● Risk {risk.score.toFixed(0)} {band ?? '-'}
      {risk.degraded ? ' ⚠' : ''}
    </Link>
  )
}

export default function GlobalIndicators() {
  const { selectedAsset } = useAssetClass()
  const { data } = useQuery<HealthSummary>({
    queryKey: ['health-summary', selectedAsset],
    queryFn: () => healthApi.getSummary({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
  })

  if (!data) {
    return <div className="text-xs text-slate-400">Loading...</div>
  }

  const allAlive = data.processes.every((p) => p.alive)
  const someAlive = data.processes.some((p) => p.alive)
  const minFreshRatio = data.data_sources.length
    ? Math.min(...data.data_sources.map((s) => s.fresh_ratio))
    : 1.0
  const killOn = data.kill_switch.enabled || data.kill_switch.active_conditions.length > 0
  const pnlPositive = data.today_pnl >= 0

  return (
    <div className="flex items-center gap-3 text-xs">
      <MarketRiskChip />
      <span
        className={`px-2 py-0.5 rounded ${
          allAlive ? 'bg-emerald-700' : someAlive ? 'bg-amber-700' : 'bg-rose-700'
        }`}
      >
        ● Process
      </span>
      <span
        className={`px-2 py-0.5 rounded ${
          minFreshRatio >= 0.8 ? 'bg-emerald-700' : 'bg-amber-700'
        }`}
      >
        ● Data {(minFreshRatio * 100).toFixed(0)}%
      </span>
      <span className={`px-2 py-0.5 rounded ${pnlPositive ? 'bg-emerald-700' : 'bg-rose-700'}`}>
        ₩{data.today_pnl.toLocaleString()}
      </span>
      <span className={`px-2 py-0.5 rounded ${killOn ? 'bg-rose-700' : 'bg-slate-700'}`}>
        Kill {killOn ? 'ON' : 'OFF'}
      </span>
    </div>
  )
}
