/**
 * LiveNotification — banner that appears when the backend detects new drift.
 * Uses the SSE hook; disappears after 8 seconds.
 */

import { useEffect, useState } from 'react'
import { AlertTriangle, Loader2, Wifi, WifiOff, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useLiveEvents } from '../hooks/useLiveEvents'
import type { LiveEvent } from '../hooks/useLiveEvents'

export function LiveNotification() {
  const { lastEvent, connected } = useLiveEvents()
  const [visible, setVisible] = useState<LiveEvent | null>(null)
  const [analyzing, setAnalyzing] = useState(false)

  useEffect(() => {
    if (!lastEvent) return

    if (lastEvent.type === 'analysis_started') {
      setAnalyzing(true)
      setVisible(null)
    } else if (lastEvent.type === 'analysis_complete' || lastEvent.type === 'drift_detected') {
      setAnalyzing(false)
      const count = (lastEvent.data.issues_found as number) ?? (lastEvent.data.count as number) ?? 0
      if (count > 0) {
        setVisible(lastEvent)
        // Auto-dismiss after 8 seconds
        const t = setTimeout(() => setVisible(null), 8000)
        return () => clearTimeout(t)
      } else {
        setVisible(null)
      }
    }
  }, [lastEvent])

  return (
    <>
      {/* Connection indicator — bottom-right corner */}
      <div className="fixed bottom-4 right-4 z-40">
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs bg-surface-card border border-surface-border">
          {connected ? (
            <>
              <Wifi size={10} className="text-green-400" />
              <span className="text-green-400">live</span>
            </>
          ) : (
            <>
              <WifiOff size={10} className="text-gray-600" />
              <span className="text-gray-600">offline</span>
            </>
          )}
          {analyzing && <Loader2 size={10} className="text-accent-light animate-spin" />}
        </div>
      </div>

      {/* Drift detected toast — top-center */}
      {visible && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-full max-w-lg px-4">
          <div className="bg-orange-900/90 backdrop-blur border border-orange-700 rounded-lg px-4 py-3 shadow-xl flex items-start gap-3">
            <AlertTriangle className="text-orange-400 flex-shrink-0 mt-0.5" size={16} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-orange-200">
                {visible.data.issues_found as number} drift issue{(visible.data.issues_found as number) !== 1 ? 's' : ''} detected
                {visible.data.repo_name ? ` in ${visible.data.repo_name}` : ''}
                {visible.data.commit ? ` (${String(visible.data.commit).slice(0, 7)})` : ''}
              </p>
              {(visible.data.issues as Array<{severity: string; description: string}>)?.slice(0, 2).map((issue, i) => (
                <p key={i} className="text-xs text-orange-300/80 truncate mt-0.5">
                  [{issue.severity}] {issue.description}
                </p>
              ))}
              <Link
                to="/drift"
                className="inline-block mt-2 text-xs text-orange-300 underline hover:text-orange-200"
                onClick={() => setVisible(null)}
              >
                View issues →
              </Link>
            </div>
            <button onClick={() => setVisible(null)} className="text-orange-500 hover:text-orange-300 flex-shrink-0">
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Analyzing indicator */}
      {analyzing && (
        <div className="fixed top-4 right-4 z-50">
          <div className="flex items-center gap-2 px-3 py-2 bg-surface-card border border-accent/40 rounded-lg text-xs text-accent-light shadow-lg">
            <Loader2 size={12} className="animate-spin" />
            Analyzing new commits…
          </div>
        </div>
      )}
    </>
  )
}
