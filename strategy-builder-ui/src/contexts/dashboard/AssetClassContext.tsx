"use client";

// Ported from dashboard-frontend/src/contexts/AssetClassContext.tsx — replaced
// react-router-dom's useSearchParams with Next.js navigation primitives.
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { useSearchParams, useRouter, usePathname } from 'next/navigation'
import { useLocalStorage } from '@/hooks/dashboard/useLocalStorage'

export type AssetClass = 'futures' | 'stock' | 'all'
const VALID: readonly AssetClass[] = ['futures', 'stock', 'all'] as const

interface AssetClassContextValue {
  selectedAsset: AssetClass
  setSelectedAsset: (asset: AssetClass) => void
}

const AssetClassContext = createContext<AssetClassContextValue | null>(null)

export const AssetClassProvider = ({ children }: { children: ReactNode }) => {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()
  const [stored, setStored] = useLocalStorage<AssetClass>('kis.asset', 'futures')

  const selectedAsset: AssetClass = useMemo(() => {
    const fromUrl = searchParams.get('asset') as AssetClass | null
    if (fromUrl && VALID.includes(fromUrl)) return fromUrl
    return stored
  }, [searchParams, stored])

  const setSelectedAsset = useCallback(
    (asset: AssetClass) => {
      // Use Next.js router.replace() to avoid pushing a history entry.
      const next = new URLSearchParams(searchParams.toString())
      next.set('asset', asset)
      router.replace(`${pathname}?${next.toString()}`, { scroll: false })
      setStored(asset)
    },
    [searchParams, router, pathname, setStored],
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
