// dashboard-frontend/src/hooks/useLocalStorage.ts
import { useCallback, useEffect, useState } from 'react'

export function useLocalStorage<T>(
  key: string,
  defaultValue: T,
): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = window.localStorage.getItem(key)
      return stored !== null ? (JSON.parse(stored) as T) : defaultValue
    } catch {
      return defaultValue
    }
  })

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value))
    } catch {
      // ignore quota errors
    }
  }, [key, value])

  const setStored = useCallback((next: T) => setValue(next), [])

  return [value, setStored]
}
