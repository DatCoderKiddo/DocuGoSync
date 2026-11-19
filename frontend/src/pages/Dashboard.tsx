import { useQuery } from '@tanstack/react-query'
import { GitBranch, AlertTriangle, FileText, Code2, CheckCircle, Clock } from 'lucide-react'
import { Link } from 'react-router-dom'
import { repositoriesApi } from '../api/repositories'
import { driftApi } from '../api/drift'
import { StatusBadge, SeverityBadge } from '../components/SeverityBadge'

export function Dashboard() {
  const repos = useQuery({ queryKey: ['repos'], queryFn: repositoriesApi.list })
  const issues = useQuery({ queryKey: ['drift', 'all'], queryFn: () => driftApi.list() })

  const totalSymbols = repos.data?.reduce((acc, r) => acc + (r.stats?.symbols ?? 0), 0) ?? 0
  const totalDocs = repos.data?.reduce((acc, r) => acc + (r.stats?.doc_sections ?? 0), 0) ?? 0
  const openIssues = issues.data?.filter(i => i.status === 'open').length ?? 0
  const resolvedIssues = issues.data?.filter(i => i.status !== 'open').length ?? 0

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-400 mt-1">Monitor documentation health across your repositories.</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Repositories"
          value={repos.data?.length ?? 0}
          icon={<GitBranch size={20} />}
          color="text-accent-light"
        />
        <StatCard
          label="Open Issues"
          value={openIssues}
          icon={<AlertTriangle size={20} />}
          color="text-orange-400"
        />
        <StatCard
          label="Code Symbols"
          value={totalSymbols}
          icon={<Code2 size={20} />}
          color="text-blue-400"
        />
        <StatCard
          label="Doc Sections"
          value={totalDocs}
          icon={<FileText size={20} />}
          color="text-green-400"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Repository list */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-200">Connected Repositories</h2>
            <Link to="/repositories" className="text-xs text-accent-light hover:underline">
              View all
            </Link>
          </div>
          {repos.isLoading && <p className="text-gray-500 text-sm">Loading…</p>}
          {repos.data?.length === 0 && (
            <div className="text-center py-6">
              <p className="text-gray-500 text-sm mb-3">No repositories connected.</p>
              <Link to="/repositories" className="btn-primary text-xs">
                Connect Repository
              </Link>
            </div>
          )}
          <div className="space-y-3">
            {repos.data?.map(repo => (
              <Link
                key={repo.id}
                to={`/repositories/${repo.id}`}
                className="flex items-center justify-between p-3 bg-surface hover:bg-surface-elevated rounded-lg transition-colors"
              >
                <div>
                  <div className="text-sm font-medium text-gray-200">{repo.name}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{repo.branch} · {repo.source}</div>
                </div>
                <div className="flex items-center gap-2">
                  {repo.stats?.open_drift_issues ? (
                    <span className="text-xs bg-orange-900/40 text-orange-300 border border-orange-800 px-2 py-0.5 rounded-full">
                      {repo.stats.open_drift_issues} issues
                    </span>
                  ) : null}
                  <StatusBadge status={repo.index_status} />
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Recent issues */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-200">Recent Drift Issues</h2>
            <Link to="/drift" className="text-xs text-accent-light hover:underline">
              View all
            </Link>
          </div>
          {issues.isLoading && <p className="text-gray-500 text-sm">Loading…</p>}
          {issues.data?.length === 0 && (
            <div className="text-center py-6">
              <CheckCircle className="mx-auto text-green-500 mb-2" size={32} />
              <p className="text-gray-400 text-sm">No drift issues detected.</p>
            </div>
          )}
          <div className="space-y-2">
            {issues.data?.slice(0, 6).map(issue => (
              <Link
                key={issue.id}
                to={`/drift/${issue.id}`}
                className="flex items-start gap-3 p-3 bg-surface hover:bg-surface-elevated rounded-lg transition-colors"
              >
                <SeverityBadge severity={issue.severity} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-300 truncate">{issue.description}</p>
                  <p className="text-xs text-gray-600 mt-0.5">{issue.doc_file_path}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({
  label, value, icon, color,
}: { label: string; value: number; icon: React.ReactNode; color: string }) {
  return (
    <div className="card p-5">
      <div className={`${color} mb-3`}>{icon}</div>
      <div className="text-2xl font-bold text-white">{value.toLocaleString()}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  )
}
