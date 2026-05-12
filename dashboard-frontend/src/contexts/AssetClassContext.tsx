// dashboard-frontend/src/contexts/AssetClassContext.tsx
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useLocalStorage } from '../hooks/useLocalStorage'

export type AssetClass = 'futures' | 'stock' | 'all'
const VALID: readonly AssetClass[] = ['futures', 'stock', 'all'] as const

interface AssetClassContextValue {
  selectedAsset: AssetClass
  setSelectedAsset: (asset: AssetClass) => void
}

const AssetClassContext = createContext<AssetClassContextValue | null>(null)

export const AssetClassProvider = ({ children }: { children: ReactNode }) => {
  const [searchParams, setSearchParams] = useSearchParams()
  const [stored, setStored] = useLocalStorage<AssetClass>('kis.asset', 'futures')

  const selectedAsset: AssetClass = useMemo(() => {
    const fromUrl = searchParams.get('asset') as AssetClass | null
    if (fromUrl && VALID.includes(fromUrl)) return fromUrl
    return stored
  }, [searchParams, stored])

  const setSelectedAsset = useCallback(
    (asset: AssetClass) => {
      setSearchParams(
        (prev) => {
          prev.set('asset', asset)
          return prev
        },
        { replace: true },
      )
      setStored(asset)
    },
    [setSearchParams, setStored],
  )

  const value = useMemo(
    () => ({ selectedAsset, setSelectedAsset }),
    [selectedAsset, setSelectedAsset],
  )

  return <AssetClassContext.Provider value={value}>{children}</AssetClassContext.Provider>
}

export const useAssetClass = (): AssetClassContextValue => {
  const ctx = useContext(AssetClassContext)
  if (!ctx) throw new Error('useAssetClass must be inside AssetClassProvider')
  return ctx
}
