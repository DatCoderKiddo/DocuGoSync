import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, ChevronRight } from 'lucide-react'
import { repositoriesApi } from '../api/repositories'
import type { DocSection } from '../types'

export function DocsPage() {
  const repos = useQuery({ queryKey: ['repos'], queryFn: repositoriesApi.list })
  const [selectedRepo, setSelectedRepo] = useState('')
  const [selectedSection, setSelectedSection] = useState<DocSection | null>(null)

  const docs = useQuery({
    queryKey: ['docs', selectedRepo],
    queryFn: () => repositoriesApi.getDocs(selectedRepo),
    enabled: !!selectedRepo,
  })

  const readyRepos = repos.data?.filter(r => r.index_status === 'ready') ?? []

  return (
    <div className="p-8 h-screen flex flex-col">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Documentation</h1>
        <p className="text-gray-400 mt-1">Browse indexed documentation sections and their content.</p>
      </div>

      <div className="mb-4">
        <select
          value={selectedRepo}
          onChange={e => setSelectedRepo(e.target.value)}
          className="bg-surface border border-surface-border rounded-md px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-accent"
        >
          <option value="">Select repository…</option>
          {readyRepos.map(r => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-0">
        {/* Section list */}
        <div className="card overflow-y-auto">
          <div className="p-3 border-b border-surface-border">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
              Sections ({docs.data?.length ?? 0})
            </span>
          </div>
          <div className="p-2 space-y-1">
            {docs.data?.map(sec => (
              <button
                key={sec.id}
                onClick={() => setSelectedSection(sec)}
                className={`w-full text-left px-3 py-2 rounded-md text-xs transition-colors flex items-center gap-2 ${
                  selectedSection?.id === sec.id
                    ? 'bg-accent/10 text-accent-light'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-surface-elevated'
                }`}
              >
                <FileText size={12} className="flex-shrink-0" />
                <div className="min-w-0">
                  <div className="font-medium truncate">{sec.heading || '(intro)'}</div>
                  <div className="text-gray-600 truncate">{sec.file_path}:{sec.start_line}</div>
                </div>
                <ChevronRight size={10} className="ml-auto flex-shrink-0" />
              </button>
            ))}
          </div>
        </div>

        {/* Section content */}
        <div className="lg:col-span-2 card overflow-y-auto">
          {selectedSection ? (
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="font-mono text-xs text-gray-500 bg-surface px-2 py-1 rounded">
                  {selectedSection.file_path}:{selectedSection.start_line}–{selectedSection.end_line}
                </div>
                <span className="text-xs text-gray-600">{selectedSection.section_type}</span>
              </div>
              {selectedSection.heading && (
                <h2 className="text-lg font-bold text-white mb-3">{selectedSection.heading}</h2>
              )}
              <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
                {selectedSection.content_preview}
              </pre>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-600">
              <p>Select a section to view its content.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
