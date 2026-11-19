import { useState } from 'react'
import { Save } from 'lucide-react'

export function Settings() {
  const [autoSync, setAutoSync] = useState(false)
  const [requireApproval, setRequireApproval] = useState(true)
  const [minConfidence, setMinConfidence] = useState(0.4)
  const [aiProvider, setAiProvider] = useState('none')
  const [saved, setSaved] = useState(false)

  const save = () => {
    // In a real implementation, POST to /api/settings
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-gray-400 mt-1">Configure drift detection and synchronization behaviour.</p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* Sync settings */}
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-gray-200 mb-5">Synchronization</h2>
          <div className="space-y-5">
            <ToggleSetting
              label="Automatic Documentation Sync"
              description="Automatically apply approved corrections when confidence exceeds threshold."
              value={autoSync}
              onChange={setAutoSync}
            />
            <ToggleSetting
              label="Require Human Approval"
              description="All corrections must be manually approved before being applied."
              value={requireApproval}
              onChange={setRequireApproval}
            />
          </div>
        </div>

        {/* Detection thresholds */}
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-gray-200 mb-5">Detection Thresholds</h2>
          <div>
            <label className="text-xs text-gray-400 block mb-2">
              Minimum Confidence to Report ({Math.round(minConfidence * 100)}%)
            </label>
            <input
              type="range"
              min="0.1"
              max="0.95"
              step="0.05"
              value={minConfidence}
              onChange={e => setMinConfidence(parseFloat(e.target.value))}
              className="w-full accent-indigo-500"
            />
            <p className="text-xs text-gray-600 mt-1">
              Issues with confidence below this threshold will be suppressed.
            </p>
          </div>
        </div>

        {/* AI configuration */}
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-gray-200 mb-5">AI Provider</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-400 block mb-2">Provider</label>
              <select
                value={aiProvider}
                onChange={e => setAiProvider(e.target.value)}
                className="w-full bg-surface border border-surface-border rounded-md px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-accent"
              >
                <option value="none">None (deterministic only)</option>
                <option value="groq">Groq (free tier)</option>
                <option value="openai">OpenAI</option>
                <option value="ollama">Ollama (local)</option>
              </select>
            </div>
            {aiProvider !== 'none' && (
              <p className="text-xs text-gray-500">
                Configure AI credentials in the <code className="font-mono bg-surface px-1 rounded">.env</code> file.
                See <code className="font-mono">.env.example</code> for available variables.
              </p>
            )}
            <div className="text-xs text-gray-600 bg-surface rounded-md p-3">
              The system works fully without an AI provider — deterministic parsing handles detection.
              AI augments correction quality for prose changes.
            </div>
          </div>
        </div>

        {/* GitHub */}
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-gray-200 mb-4">GitHub Integration</h2>
          <p className="text-xs text-gray-500 mb-3">
            For Phase 3: webhook-triggered analysis and automatic PR creation.
          </p>
          <div className="text-xs text-gray-600 bg-surface rounded-md p-3">
            Set <code className="font-mono">GITHUB_TOKEN</code>,{' '}
            <code className="font-mono">GITHUB_WEBHOOK_SECRET</code>, and optionally{' '}
            <code className="font-mono">GITHUB_APP_ID</code> in your <code className="font-mono">.env</code> file.
          </div>
        </div>

        <button onClick={save} className="btn-primary flex items-center gap-2">
          <Save size={14} />
          {saved ? 'Saved!' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}

function ToggleSetting({
  label, description, value, onChange,
}: { label: string; description: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-start justify-between gap-6">
      <div>
        <div className="text-sm text-gray-200">{label}</div>
        <div className="text-xs text-gray-500 mt-0.5">{description}</div>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors ${
          value ? 'bg-accent' : 'bg-surface-border'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform mt-0.5 ${
            value ? 'translate-x-4.5' : 'translate-x-0.5'
          }`}
        />
      </button>
    </div>
  )
}
