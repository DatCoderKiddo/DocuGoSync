import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Zap, AlertCircle, CheckCircle } from 'lucide-react'
import { repositoriesApi } from '../api/repositories'
import { driftApi } from '../api/drift'
import { DriftIssueCard } from '../components/DriftIssueCard'
import type { DriftIssue } from '../types'

export function Analyze() {
  const repos = useQuery({ queryKey: ['repos'], queryFn: repositoriesApi.list })
  const [repoId, setRepoId] = useState('')
  const [oldCode, setOldCode] = useState('')
  const [newCode, setNewCode] = useState('')
  const [codeFile, setCodeFile] = useState('src/main.py')
  const [docContent, setDocContent] = useState('')
  const [docFile, setDocFile] = useState('README.md')
  const [results, setResults] = useState<DriftIssue[]>([])

  const analyze = useMutation({
    mutationFn: () =>
      driftApi.analyzeFiles(
        repoId,
        [{ path: codeFile, old_content: oldCode, new_content: newCode }],
        docFile,
      ),
    onSuccess: (data) => {
      setResults(data.issues || [])
    },
  })

  const readyRepos = repos.data?.filter(r => r.index_status === 'ready') ?? []

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Analyze Code Changes</h1>
        <p className="text-gray-400 mt-1">
          Paste old and new code to detect documentation drift immediately.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6">
        {/* Configuration */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-200 mb-4">Configuration</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Repository</label>
              <select
                value={repoId}
                onChange={e => setRepoId(e.target.value)}
                className="w-full bg-surface border border-surface-border rounded-md px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-accent"
              >
                <option value="">Select a repository…</option>
                {readyRepos.map(r => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Code File Path</label>
                <input
                  value={codeFile}
                  onChange={e => setCodeFile(e.target.value)}
                  className="w-full bg-surface border border-surface-border rounded-md px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Doc File Path</label>
                <input
                  value={docFile}
                  onChange={e => setDocFile(e.target.value)}
                  className="w-full bg-surface border border-surface-border rounded-md px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-accent"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Quick test fixture */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-200 mb-4">Quick Test Fixture</h2>
          <p className="text-xs text-gray-500 mb-3">Load a sample scenario to test drift detection.</p>
          <div className="space-y-2">
            {Object.entries(FIXTURES).map(([key, fixture]) => (
              <button
                key={key}
                onClick={() => {
                  setOldCode(fixture.old)
                  setNewCode(fixture.new)
                  setDocContent(fixture.doc)
                }}
                className="w-full text-left px-3 py-2 bg-surface hover:bg-surface-elevated border border-surface-border rounded-md text-xs text-gray-300 transition-colors"
              >
                <span className="font-medium">{fixture.label}</span>
                <span className="text-gray-500 ml-2">— {fixture.description}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Code editors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div>
          <label className="text-xs font-semibold text-red-400 uppercase tracking-wide mb-2 block">
            Old Code (before change)
          </label>
          <textarea
            value={oldCode}
            onChange={e => setOldCode(e.target.value)}
            rows={14}
            className="w-full font-mono text-xs bg-surface border border-surface-border rounded-lg px-4 py-3 text-red-300 focus:outline-none focus:border-red-700 resize-none"
            placeholder="# Paste the original version of the changed code here"
          />
        </div>
        <div>
          <label className="text-xs font-semibold text-green-400 uppercase tracking-wide mb-2 block">
            New Code (after change)
          </label>
          <textarea
            value={newCode}
            onChange={e => setNewCode(e.target.value)}
            rows={14}
            className="w-full font-mono text-xs bg-surface border border-surface-border rounded-lg px-4 py-3 text-green-300 focus:outline-none focus:border-green-700 resize-none"
            placeholder="# Paste the updated version of the changed code here"
          />
        </div>
      </div>

      {/* Analyze button */}
      <div className="flex items-center gap-4 mb-8">
        <button
          onClick={() => analyze.mutate()}
          disabled={!repoId || !oldCode || !newCode || analyze.isPending}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          <Zap size={16} />
          {analyze.isPending ? 'Analyzing…' : 'Detect Drift'}
        </button>
        {analyze.isError && (
          <span className="text-red-400 text-sm flex items-center gap-1">
            <AlertCircle size={14} />
            {(analyze.error as any)?.response?.data?.detail || 'Analysis failed'}
          </span>
        )}
        {analyze.isSuccess && results.length === 0 && (
          <span className="text-green-400 text-sm flex items-center gap-1">
            <CheckCircle size={14} />
            No drift detected.
          </span>
        )}
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div>
          <h2 className="text-lg font-bold text-white mb-4">
            {results.length} Drift Issue{results.length !== 1 ? 's' : ''} Detected
          </h2>
          <div className="space-y-3">
            {results.map(issue => (
              <DriftIssueCard key={issue.id} issue={issue} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

const FIXTURES: Record<string, { label: string; description: string; old: string; new: string; doc: string }> = {
  signature: {
    label: 'Function signature change',
    description: 'Parameter added',
    old: `def login(username, password):
    """Authenticate a user."""
    return authenticate(username, password)`,
    new: `def login(username, password, remember=False, mfa_code=None):
    """Authenticate a user with optional MFA."""
    return authenticate(username, password, remember, mfa_code)`,
    doc: `## Authentication

Use the \`login(username, password)\` function to authenticate users.

Parameters:
- \`username\` - The user's email address
- \`password\` - The user's password`,
  },
  default: {
    label: 'Default value change',
    description: 'Timeout changed from 30 to 60',
    old: `def fetch_data(url, timeout=30, retries=3):
    """Fetch data from the given URL."""
    pass`,
    new: `def fetch_data(url, timeout=60, retries=3):
    """Fetch data from the given URL."""
    pass`,
    doc: `## Data Fetching

Call \`fetch_data(url, timeout=30, retries=3)\` to retrieve data.

The default timeout is 30 seconds.`,
  },
  removed: {
    label: 'Function removed',
    description: 'Deprecated function deleted',
    old: `def legacy_auth(token):
    """Deprecated: use login() instead."""
    pass

def login(username, password):
    pass`,
    new: `def login(username, password):
    pass`,
    doc: `## Authentication

You can use \`legacy_auth(token)\` for token-based authentication (deprecated).

Or use \`login(username, password)\` for the modern flow.`,
  },
}
