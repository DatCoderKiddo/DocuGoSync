import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Filter } from 'lucide-react'
import { driftApi } from '../api/drift'
import { DriftIssueCard } from '../components/DriftIssueCard'

const SEVERITIES = ['all', 'critical', 'high', 'medium', 'low']
const STATUSES = ['all', 'open', 'approved', 'rejected', 'applied']

export function DriftIssues() {
  const [severity, setSeverity] = useState('all')
  const [status, setStatus] = useState('open')

  const issues = useQuery({
    queryKey: ['drift', severity, status],
    queryFn: () =>
      driftApi.list({
        severity: severity !== 'all' ? severity : undefined,
        status: status !== 'all' ? status : undefined,
      }),
  })

  const counts = {
    critical: issues.data?.filter(i => i.severity === 'critical').length ?? 0,
    high: issues.data?.filter(i => i.severity === 'high').length ?? 0,
    medium: issues.data?.filter(i => i.severity === 'medium').length ?? 0,
    low: issues.data?.filter(i => i.severity === 'low').length ?? 0,
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Drift Issues</h1>
        <p className="text-gray-400 mt-1">Documentation sections that no longer match the code.</p>
      </div>

      {/* Severity summary */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {(['critical', 'high', 'medium', 'low'] as const).map(sev => (
          <button
            key={sev}
            onClick={() => setSeverity(sev === severity ? 'all' : sev)}
            className={`card p-4 text-left hover:bg-surface-elevated transition-colors ${severity === sev ? 'ring-1 ring-accent' : ''}`}
          >
            <div className={`text-2xl font-bold ${
              sev === 'critical' ? 'text-red-400' :
              sev === 'high' ? 'text-orange-400' :
              sev === 'medium' ? 'text-yellow-400' : 'text-green-400'
            }`}>
              {counts[sev]}
            </div>
            <div className="text-xs text-gray-500 mt-1 capitalize">{sev}</div>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-5">
        <Filter size={14} className="text-gray-500" />
        <div className="flex gap-2">
          {STATUSES.map(s => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                status === s
                  ? 'bg-accent border-accent text-white'
                  : 'border-surface-border text-gray-400 hover:text-gray-200'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Issues */}
      {issues.isLoading && (
        <div className="text-center py-12 text-gray-500">Loading issues…</div>
      )}

      {!issues.isLoading && issues.data?.length === 0 && (
        <div className="text-center py-16">
          <AlertTriangle className="mx-auto text-gray-700 mb-3" size={48} />
          <p className="text-gray-400">No issues found for the current filters.</p>
        </div>
      )}

      <div className="space-y-3">
        {issues.data?.map(issue => (
          <DriftIssueCard key={issue.id} issue={issue} />
        ))}
      </div>
    </div>
  )
}
