import clsx from 'clsx'

type Severity = 'critical' | 'high' | 'medium' | 'low'

const labels: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={clsx('badge', `badge-${severity}`)}>
      {labels[severity]}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    open: 'bg-blue-900/40 text-blue-300 border-blue-800',
    approved: 'bg-green-900/40 text-green-300 border-green-800',
    rejected: 'bg-red-900/40 text-red-300 border-red-800',
    applied: 'bg-purple-900/40 text-purple-300 border-purple-800',
    pending: 'bg-gray-800/40 text-gray-400 border-gray-700',
    indexing: 'bg-blue-900/40 text-blue-300 border-blue-800',
    ready: 'bg-green-900/40 text-green-300 border-green-800',
    error: 'bg-red-900/40 text-red-300 border-red-800',
  }
  return (
    <span className={clsx('badge border', styles[status] || styles.pending)}>
      {status}
    </span>
  )
}
