import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Webhook, Radio, CheckCircle, AlertCircle, ExternalLink, Copy } from 'lucide-react'
import api from '../api/client'
import { useLiveEvents } from '../hooks/useLiveEvents'

function usePollingStatus() {
  return useQuery({
    queryKey: ['polling-status'],
    queryFn: () => api.get('/github/polling/status').then(r => r.data),
    refetchInterval: 10_000,
  })
}

function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health').then(r => r.data),
    refetchInterval: 15_000,
  })
}

export function AutoTracking() {
  const qc = useQueryClient()
  const status = usePollingStatus()
  const health = useHealth()
  const { connected, lastEvent } = useLiveEvents()

  const triggerPoll = useMutation({
    mutationFn: () => api.post('/github/polling/trigger').then(r => r.data),
    onSuccess: () =>
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['polling-status'] })
        qc.invalidateQueries({ queryKey: ['drift'] })
      }, 3000),
  })

  const autoTracking = (health.data?.auto_tracking ?? {}) as Record<string, unknown>
  const webhookActive = Boolean(autoTracking.webhook)
  const pollingActive = Boolean(autoTracking.polling)
  const pollingInterval = (autoTracking.polling_interval_seconds as number) ?? 60

  const webhookUrl = `${window.location.protocol}//${window.location.host}/api/github/webhook`

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Auto Tracking</h1>
        <p className="text-gray-400 mt-1">
          Automatic drift detection on every commit — no manual triggers.
        </p>
      </div>

      {/* Live connection indicator */}
      <div className="card p-4 mb-6 flex items-center gap-3">
        <div
          className={`w-2 h-2 rounded-full flex-shrink-0 ${
            connected ? 'bg-green-400 animate-pulse' : 'bg-gray-600'
          }`}
        />
        <div className="flex-1">
          <p className="text-sm text-gray-200">
            {connected
              ? 'Live stream connected — results appear the instant analysis completes'
              : 'Not connected to live stream'}
          </p>
          {lastEvent && (
            <p className="text-xs text-gray-500 mt-0.5">
              Last event: <span className="text-gray-400">{lastEvent.type}</span>
              {' · '}
              {new Date(lastEvent.ts).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>

      {/* How it works */}
      <div className="card p-5 mb-6">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">
          How automatic tracking works
        </h2>
        <div className="flex items-start gap-6">
          {[
            { n: '1', label: 'Commit pushed', desc: 'Developer pushes to GitHub' },
            { n: '2', label: 'DocuGoSync notified', desc: 'Webhook or poller detects the change' },
            { n: '3', label: 'Diff extracted', desc: 'Changed symbols are identified' },
            { n: '4', label: 'Drift detected', desc: 'Outdated docs flagged with evidence' },
            { n: '5', label: 'You review', desc: 'Approve or reject in the dashboard' },
          ].map((step) => (
            <div key={step.n} className="flex-1 text-center">
              <div className="w-7 h-7 rounded-full bg-accent/20 border border-accent/40 text-accent-light text-xs font-bold flex items-center justify-center mx-auto mb-2">
                {step.n}
              </div>
              <p className="text-xs font-medium text-gray-300">{step.label}</p>
              <p className="text-xs text-gray-600 mt-0.5">{step.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Option A — Webhook */}
      <div className="card p-6 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Webhook className="text-accent-light" size={18} />
            <div>
              <h2 className="text-sm font-semibold text-gray-200">
                Option A — GitHub Webhook
              </h2>
              <p className="text-xs text-gray-500">
                Instant. Triggered the moment you push. Best for production.
              </p>
            </div>
          </div>
          {webhookActive ? (
            <span className="flex items-center gap-1 text-green-400 text-xs">
              <CheckCircle size={12} /> Active
            </span>
          ) : (
            <span className="flex items-center gap-1 text-gray-500 text-xs">
              <AlertCircle size={12} /> Not configured
            </span>
          )}
        </div>

        <div className="space-y-3">
          <p className="text-xs text-gray-400">
            Go to your GitHub repo → <strong className="text-gray-300">Settings → Webhooks → Add webhook</strong> and use:
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-surface border border-surface-border rounded px-3 py-2 font-mono text-xs text-green-400 truncate">
              {webhookUrl}
            </code>
            <button
              onClick={() => navigator.clipboard.writeText(webhookUrl)}
              className="btn-secondary p-2 flex-shrink-0"
              title="Copy"
            >
              <Copy size={13} />
            </button>
          </div>

          <div className="text-xs text-gray-500 space-y-1 ml-1">
            <p>• Content type: <code className="bg-surface px-1 rounded">application/json</code></p>
            <p>
              • Secret: set <code className="bg-surface px-1 rounded">GITHUB_WEBHOOK_SECRET</code> in{' '}
              <code className="bg-surface px-1 rounded">.env</code> — must match what you enter in GitHub
            </p>
            <p>• Events to send: <strong className="text-gray-400">Pushes</strong> and <strong className="text-gray-400">Pull requests</strong></p>
            <p>
              • Running locally?{' '}
              <a
                href="https://ngrok.com/download"
                target="_blank"
                rel="noreferrer"
                className="text-accent-light hover:underline inline-flex items-center gap-0.5"
              >
                Use ngrok to expose a public URL <ExternalLink size={9} />
              </a>
              {' '}→{' '}
              <code className="bg-surface px-1 rounded">ngrok http 8000</code>
            </p>
          </div>
        </div>
      </div>

      {/* Option B — Polling */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Radio className="text-accent-light" size={18} />
            <div>
              <h2 className="text-sm font-semibold text-gray-200">
                Option B — Automatic Polling
              </h2>
              <p className="text-xs text-gray-500">
                Checks GitHub every {pollingInterval}s. No public URL needed. Great for local dev.
              </p>
            </div>
          </div>
          {pollingActive ? (
            <span className="flex items-center gap-1 text-green-400 text-xs">
              <CheckCircle size={12} /> Running
            </span>
          ) : (
            <span className="flex items-center gap-1 text-gray-500 text-xs">
              <AlertCircle size={12} /> Inactive
            </span>
          )}
        </div>

        <p className="text-xs text-gray-400 mb-2">
          Add to your <code className="bg-surface px-1 rounded font-mono">.env</code> and restart the backend:
        </p>
        <pre className="bg-surface border border-surface-border rounded px-4 py-3 text-xs font-mono text-green-400 mb-3 overflow-x-auto">
{`GITHUB_TOKEN=ghp_your_token_here
POLLING_ENABLED=true
POLLING_INTERVAL_SECONDS=60`}
        </pre>
        <p className="text-xs text-gray-600">
          A read-only token (<code className="bg-surface px-1 rounded">public_repo</code> scope) is enough —
          DocuGoSync only reads commit metadata and clones code.
        </p>

        {/* Tracked repos list */}
        {(status.data?.tracked_repos?.length ?? 0) > 0 && (
          <div className="mt-5 border-t border-surface-border pt-4">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Currently tracked
            </p>
            <div className="space-y-2">
              {(status.data?.tracked_repos as Array<Record<string, string>>).map((repo) => (
                <div
                  key={repo.id}
                  className="flex items-center justify-between px-3 py-2 bg-surface rounded text-xs"
                >
                  <span className="text-gray-300 font-medium">{repo.name}</span>
                  <div className="flex items-center gap-4 text-gray-500">
                    <span>{repo.branch}</span>
                    <span className="font-mono">{repo.head_commit?.slice(0, 7) ?? '—'}</span>
                    {repo.last_checked && (
                      <span>
                        checked {new Date(repo.last_checked).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Manual trigger */}
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => triggerPoll.mutate()}
            disabled={triggerPoll.isPending}
            className="btn-secondary flex items-center gap-2 text-xs"
          >
            <RefreshCw size={13} className={triggerPoll.isPending ? 'animate-spin' : ''} />
            {triggerPoll.isPending ? 'Polling…' : 'Poll now'}
          </button>
          <span className="text-xs text-gray-600">
            Manually run one poll cycle immediately
          </span>
          {triggerPoll.isSuccess && (
            <span className="text-xs text-green-400 flex items-center gap-1">
              <CheckCircle size={11} /> Triggered
            </span>
          )}
        </div>
      </div>

      {/* Quick comparison table */}
      <div className="card p-5">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">
          Which option to use?
        </h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-surface-border">
              <th className="text-left pb-2">Feature</th>
              <th className="text-center pb-2">Webhook</th>
              <th className="text-center pb-2">Polling</th>
            </tr>
          </thead>
          <tbody className="text-gray-400">
            {[
              ['Speed', 'Instant', `Every ${pollingInterval}s`],
              ['Needs public URL', 'Yes (or ngrok)', 'No'],
              ['GitHub token needed', 'No', 'Yes'],
              ['Works on localhost', 'With ngrok', 'Yes, natively'],
              ['PR analysis', 'Yes', 'Push only'],
              ['Setup effort', 'Medium', 'Low'],
            ].map(([feature, webhook, polling]) => (
              <tr key={feature} className="border-b border-surface-border/40">
                <td className="py-2 text-gray-300">{feature}</td>
                <td className="py-2 text-center">{webhook}</td>
                <td className="py-2 text-center">{polling}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
