/**
 * useLiveEvents — subscribes to the backend SSE stream and returns
 * the most recent event.  Components can use this to show real-time
 * notifications when new drift is detected without manual refresh.
 */

import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export interface LiveEvent {
  type: 'analysis_started' | 'analysis_complete' | 'drift_detected' | 'connected'
  data: Record<string, unknown>
  ts: number
}

export function useLiveEvents() {
  const [lastEvent, setLastEvent] = useState<LiveEvent | null>(null)
  const [connected, setConnected] = useState(false)
  const qc = useQueryClient()
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/events')
    esRef.current = es

    es.addEventListener('connected', () => {
      setConnected(true)
    })

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data) as { type: string; data: Record<string, unknown> }
        const event: LiveEvent = { ...payload as any, ts: Date.now() }
        setLastEvent(event)

        // Automatically invalidate relevant queries so UI refreshes
        if (payload.type === 'drift_detected' || payload.type === 'analysis_complete') {
          qc.invalidateQueries({ queryKey: ['drift'] })
          qc.invalidateQueries({ queryKey: ['repos'] })
          if (payload.data.repo_id) {
            qc.invalidateQueries({ queryKey: ['repo', payload.data.repo_id] })
          }
        }
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      setConnected(false)
      // EventSource reconnects automatically — no manual retry needed
    }

    return () => {
      es.close()
      setConnected(false)
    }
  }, [qc])

  return { lastEvent, connected }
}
