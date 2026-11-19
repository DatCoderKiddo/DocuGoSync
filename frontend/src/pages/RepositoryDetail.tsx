import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Code2, FileText, Link2, AlertTriangle } from 'lucide-react'
import { repositoriesApi } from '../api/repositories'
import { driftApi } from '../api/drift'
import { StatusBadge, SeverityBadge } from '../components/SeverityBadge'

export function RepositoryDetail() {
  const { id } = useParams<{ id: string }>()

  const repo = useQuery({
    queryKey: ['repo', id],
    queryFn: () => repositoriesApi.get(id!),
    enabled: !!id,
  })

  const symbols = useQuery({
    queryKey: ['repo', id, 'symbols'],
    queryFn: () => repositoriesApi.getSymbols(id!),
    enabled: !!id && repo.data?.index_status === 'ready',
  })

  const docs = useQuery({
    queryKey: ['repo', id, 'docs'],
    queryFn: () => repositoriesApi.getDocs(id!),
    enabled: !!id && repo.data?.index_status === 'ready',
  })

  const mappings = useQuery({
    queryKey: ['repo', id, 'mappings'],
    queryFn: () => repositoriesApi.getMappings(id!),
    enabled: !!id && repo.data?.index_status === 'ready',
  })

  const issues = useQuery({
    queryKey: ['drift', id],
    queryFn: () => driftApi.list({ repo_id: id }),
    enabled: !!id,
  })

  if (repo.isLoading) return <div className="p-8 text-gray-500">Loading…</div>
  if (!repo.data) return <div className="p-8 text-red-400">Repository not found.</div>

  const r = repo.data

  return (
    <div className="p-8">
      <Link to="/repositories" className="flex items-center gap-2 text-gray-500 hover:text-gray-300 text-sm mb-6">
        <ArrowLeft size={14} />
        All Repositories
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-white">{r.name}</h1>
            <StatusBadge status={r.index_status} />
          </div>
          <p className="text-gray-500 text-sm">
            {r.branch} · {r.source} {r.url && `· ${r.url}`}
          </p>
        </div>
        <Link to="/analyze" className="btn-secondary flex items-center gap-2 text-sm">
          <AlertTriangle size={14} />
          Analyze Changes
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <Stat label="Code Symbols" value={r.stats?.symbols ?? 0} icon={<Code2 size={16} />} />
        <Stat label="Doc Sections" value={r.stats?.doc_sections ?? 0} icon={<FileText size={16} />} />
        <Stat label="Mappings" value={r.stats?.mappings ?? 0} icon={<Link2 size={16} />} />
        <Stat label="Open Issues" value={r.stats?.open_drift_issues ?? 0} icon={<AlertTriangle size={16} />} accent />
      </div>

      {r.index_status === 'error' && (
        <div className="card p-4 border-red-800 mb-6">
          <p className="text-red-400 text-sm">{r.error_message}</p>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Code symbols */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <Code2 size={14} />
            Code Symbols ({symbols.data?.length ?? 0})
          </h2>
          <div className="max-h-72 overflow-y-auto space-y-1">
            {symbols.data?.slice(0, 50).map(sym => (
              <div key={sym.id} className="flex items-center gap-3 py-1.5 px-2 hover:bg-surface-elevated rounded text-xs">
                <span className="text-gray-600 font-mono bg-surface px-1.5 py-0.5 rounded text-[10px]">
                  {sym.symbol_type}
                </span>
                <span className="font-mono text-gray-300 truncate">{sym.name}</span>
                <span className="text-gray-600 ml-auto truncate">{sym.file_path}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Doc sections */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <FileText size={14} />
            Documentation Sections ({docs.data?.length ?? 0})
          </h2>
          <div className="max-h-72 overflow-y-auto space-y-1">
            {docs.data?.map(sec => (
              <div key={sec.id} className="py-1.5 px-2 hover:bg-surface-elevated rounded text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-gray-500 font-mono">{sec.file_path}:{sec.start_line}</span>
                  {sec.heading && (
                    <span className="text-gray-300 font-medium truncate">{sec.heading}</span>
                  )}
                </div>
                <p className="text-gray-600 truncate mt-0.5">{sec.content_preview}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Mappings */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <Link2 size={14} />
            Code → Doc Mappings ({mappings.data?.length ?? 0})
          </h2>
          <div className="max-h-72 overflow-y-auto space-y-1">
            {mappings.data?.map(m => (
              <div key={m.id} className="py-1.5 px-2 hover:bg-surface-elevated rounded text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-accent-light">{m.symbol_name}</span>
                  <span className="text-gray-600">→</span>
                  <span className="text-gray-400">{m.doc_heading || m.doc_file}</span>
                  <span className="ml-auto text-gray-600">{Math.round(m.confidence * 100)}%</span>
                </div>
                <p className="text-gray-600 mt-0.5">{m.evidence_detail}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Drift issues */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <AlertTriangle size={14} />
            Drift Issues ({issues.data?.length ?? 0})
          </h2>
          <div className="max-h-72 overflow-y-auto space-y-2">
            {issues.data?.map(issue => (
              <Link
                key={issue.id}
                to={`/drift/${issue.id}`}
                className="flex items-start gap-3 py-2 px-2 hover:bg-surface-elevated rounded"
              >
                <SeverityBadge severity={issue.severity} />
                <p className="text-xs text-gray-300 leading-snug">{issue.description}</p>
              </Link>
            ))}
            {issues.data?.length === 0 && (
              <p className="text-gray-600 text-xs text-center py-4">No issues found.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Stat({
  label, value, icon, accent,
}: { label: string; value: number; icon: React.ReactNode; accent?: boolean }) {
  return (
    <div className="card p-4">
      <div className={`${accent ? 'text-orange-400' : 'text-gray-500'} mb-2`}>{icon}</div>
      <div className={`text-xl font-bold ${accent ? 'text-orange-400' : 'text-white'}`}>
        {value}
      </div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  )
}
