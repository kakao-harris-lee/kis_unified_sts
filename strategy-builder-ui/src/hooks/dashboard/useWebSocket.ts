import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 16000, 30000]
const SUBSCRIPTIONS = ['positions', 'signals', 'fills', 'data-freshness', 'kill-switch']

export function useWebSocketInvalidation() {
  const queryClient = useQueryClient()

  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectIdx = 0
    let stopped = false
    let timeout: number | null = null

    const connect = () => {
      if (stopped) return
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const url = new URL(`${protocol}//${window.location.host}/ws`)
      const apiKey = process.env.NEXT_PUBLIC_API_KEY
      if (apiKey) url.searchParams.set('api_key', apiKey)
      ws = new WebSocket(url.toString())

      ws.onopen = () => {
        reconnectIdx = 0
        SUBSCRIPTIONS.forEach((channel) => {
          ws?.send(JSON.stringify({ type: 'subscribe', channel }))
        })
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          const { topic, asset_class } = msg
          if (!topic) return
          queryClient.invalidateQueries({ queryKey: [topic, asset_class] })
          queryClient.invalidateQueries({ queryKey: [topic, 'all'] })
          if (topic === 'kill-switch' || topic === 'data-freshness') {
            queryClient.invalidateQueries({ queryKey: ['health-summary'] })
          }
        } catch {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        if (stopped) return
        const delay =
          RECONNECT_DELAYS_MS[Math.min(reconnectIdx, RECONNECT_DELAYS_MS.length - 1)]
        reconnectIdx += 1
        timeout = window.setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      if (timeout !== null) window.clearTimeout(timeout)
      if (ws) ws.close()
    }
  }, [queryClient])
}
