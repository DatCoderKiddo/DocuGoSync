import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Upload, GitBranch, RefreshCw, Trash2, ExternalLink } from 'lucide-react'
import { repositoriesApi } from '../api/repositories'
import { StatusBadge } from '../components/SeverityBadge'

export function Repositories() {
  const qc = useQueryClient()
  const [showConnect, setShowConnect] = useState(false)
  const [url, setUrl] = useState('')
  const [branch, setBranch] = useState('main')
  const [uploadFile, setUploadFile] = useState<File | null>(null)

  const repos = useQuery({ queryKey: ['repos'], queryFn: repositoriesApi.list })

  const connect = useMutation({
    mutationFn: () => repositoriesApi.connect(url, branch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['repos'] })
      setUrl('')
      setShowConnect(false)
    },
  })

  const upload = useMutation({
    mutationFn: () => repositoriesApi.uploadZip(uploadFile!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['repos'] })
      setUploadFile(null)
    },
  })

  const reindex = useMutation({
    mutationFn: (id: string) => repositoriesApi.reindex(id),
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ['repos'] }), 1000),
  })

  const del = useMutation({
    mutationFn: (id: string) => repositoriesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['repos'] }),
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Repositories</h1>
          <p className="text-gray-400 mt-1">Connect and manage repositories for drift detection.</p>
        </div>
        <button onClick={() => setShowConnect(!showConnect)} className="btn-primary flex items-center gap-2">
          <Plus size={16} />
          Connect Repository
        </button>
      </div>

      {/* Connect form */}
      {showConnect && (
        <div className="card p-6 mb-6">
          <h2 className="text-sm font-semibold text-gray-200 mb-4">Connect Repository</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* GitHub URL */}
            <div>
              <h3 className="text-xs font-medium text-gray-400 mb-3 flex items-center gap-2">
                <GitBranch size={14} />
                GitHub URL
              </h3>
              <input
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="w-full bg-surface border border-surface-border rounded-md px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-accent"
              />
              <input
                value={branch}
                onChange={e => setBranch(e.target.value)}
                placeholder="Branch (default: main)"
                className="w-full mt-2 bg-surface border border-surface-border rounded-md px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-accent"
              />
              <button
                onClick={() => connect.mutate()}
                disabled={!url || connect.isPending}
                className="mt-3 btn-primary disabled:opacity-50"
              >
                {connect.isPending ? 'Connecting…' : 'Connect'}
              </button>
              {connect.isError && (
                <p className="text-red-400 text-xs mt-2">
                  {(connect.error as any)?.response?.data?.detail || 'Connection failed'}
                </p>
              )}
            </div>

            {/* ZIP upload */}
            <div>
              <h3 className="text-xs font-medium text-gray-400 mb-3 flex items-center gap-2">
                <Upload size={14} />
                Upload ZIP Archive
              </h3>
              <label className="block w-full border-2 border-dashed border-surface-border rounded-lg p-6 text-center cursor-pointer hover:border-accent/50 transition-colors">
                <Upload className="mx-auto text-gray-500 mb-2" size={24} />
                <span className="text-sm text-gray-400">
                  {uploadFile ? uploadFile.name : 'Drop ZIP file here or click to browse'}
                </span>
                <input
                  type="file"
                  accept=".zip"
                  className="hidden"
                  onChange={e => setUploadFile(e.target.files?.[0] ?? null)}
                />
              </label>
              <button
                onClick={() => upload.mutate()}
                disabled={!uploadFile || upload.isPending}
                className="mt-3 btn-primary disabled:opacity-50"
              >
                {upload.isPending ? 'Uploading…' : 'Upload & Index'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Repository list */}
      {repos.isLoading && <p className="text-gray-500">Loading repositories…</p>}
      <div className="space-y-3">
        {repos.data?.map(repo => (
          <div key={repo.id} className="card p-5">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <Link to={`/repositories/${repo.id}`} className="text-white font-semibold hover:text-accent-light">
                    {repo.name}
                  </Link>
                  <StatusBadge status={repo.index_status} />
                  <span className="text-xs text-gray-600">{repo.branch}</span>
                </div>
                {repo.url && (
                  <a href={repo.url} target="_blank" rel="noreferrer"
                    className="text-xs text-gray-500 hover:text-accent-light flex items-center gap-1">
                    <ExternalLink size={10} />
                    {repo.url}
                  </a>
                )}
                {repo.stats && (
                  <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                    <span>{repo.stats.symbols} symbols</span>
                    <span>{repo.stats.doc_sections} doc sections</span>
                    <span>{repo.stats.mappings} mappings</span>
                    {repo.stats.open_drift_issues > 0 && (
                      <span className="text-orange-400 font-medium">
                        {repo.stats.open_drift_issues} open issues
                      </span>
                    )}
                  </div>
                )}
                {repo.error_message && (
                  <p className="text-red-400 text-xs mt-2">{repo.error_message}</p>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => reindex.mutate(repo.id)}
                  className="btn-secondary p-2"
                  title="Re-index"
                >
                  <RefreshCw size={14} />
                </button>
                <button
                  onClick={() => { if (confirm('Delete this repository?')) del.mutate(repo.id) }}
                  className="p-2 bg-surface hover:bg-red-900/40 border border-surface-border hover:border-red-800 text-gray-400 hover:text-red-300 rounded-md transition-colors"
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {repos.data?.length === 0 && !repos.isLoading && (
        <div className="text-center py-16">
          <GitBranch className="mx-auto text-gray-700 mb-3" size={48} />
          <p className="text-gray-400">No repositories connected yet.</p>
          <p className="text-gray-600 text-sm mt-1">Connect a GitHub repo or upload a ZIP to get started.</p>
        </div>
      )}
    </div>
  )
}
