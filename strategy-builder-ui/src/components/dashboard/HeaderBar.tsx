import AssetClassTabs from './AssetClassTabs'
import ColorConventionLegend from './ColorConventionLegend'
import GlobalIndicators from './GlobalIndicators'

export default function HeaderBar() {
  return (
    <header className="sticky top-0 z-30 bg-slate-900 text-slate-100 px-3 py-2 shadow-md">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-sm">KIS Cockpit</span>
          <div className="w-48 sm:w-64">
            <AssetClassTabs />
          </div>
        </div>
        <div className="sm:ml-auto flex items-center gap-3">
          <ColorConventionLegend />
          <GlobalIndicators />
        </div>
      </div>
    </header>
  )
}
