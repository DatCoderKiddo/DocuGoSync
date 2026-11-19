import { useState } from 'react'
import {
  ChevronDown, ChevronUp, CheckCircle, XCircle, FileText, Code2,
  AlertTriangle, Info,
} from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { SeverityBadge, StatusBadge } from './SeverityBadge'
import { driftApi } from '../api/drift'
import type { DriftIssue } from '../types'

interface Props {
  issue: DriftIssue
}

export function DriftIssueCard({ issue }: Props) {
  const [expanded, setExpanded] = useState(false)
  const qc = useQueryClient()

  const updateStatus = useMutation({
    mutationFn: (status: string) => driftApi.updateStatus(issue.id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['drift'] })
      qc.invalidateQueries({ queryKey: ['drift', issue.id] })
    },
  })

  const applyPatch = useMutation({
    mutationFn: () => driftApi.applyPatch(issue.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['drift'] })
    },
  })

  return (
    <div className={clsx(
      'card overflow-hidden',
      issue.status === 'applied' && 'opacity-60',
    )}>
      {/* Header row */}
      <div
        className="flex items-start gap-4 p-4 cursor-pointer hover:bg-surface-elevated/40 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <SeverityBadge severity={issue.severity} />
            <StatusBadge status={issue.status} />
            <span className="text-xs text-gray-500 font-mono bg-surface px-2 py-0.5 rounded">
              {issue.issue_type}
            </span>
            <span className="text-xs text-gray-600 ml-auto">
              {Math.round(issue.confidence * 100)}% confidence
            </span>
          </div>
          <p className="text-sm text-gray-200 font-medium leading-snug">
            {issue.description}
          </p>
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <FileText size={12} />
              {issue.doc_file_path}:{issue.doc_start_line}
            </span>
            {issue.code_file_path && (
              <span className="flex items-center gap-1">
                <Code2 size={12} />
                {issue.code_file_path}
              </span>
            )}
          </div>
        </div>
        <div className="flex-shrink-0 text-gray-500">
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-surface-border">
          {/* Evidence */}
          <div className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                <Code2 size={12} />
                Current Code
              </div>
              <pre className="code-block text-xs overflow-x-auto whitespace-pre-wrap">
                {issue.evidence_code || '(no code evidence)'}
              </pre>
            </div>
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                <AlertTriangle size={12} />
                Outdated Documentation
              </div>
              <pre className="code-block text-red-400 text-xs overflow-x-auto whitespace-pre-wrap">
                {issue.evidence_doc || '(no doc evidence)'}
              </pre>
            </div>
          </div>

          {/* Suggested correction */}
          {issue.suggested_correction && issue.suggested_correction !== '[Review needed: insufficient evidence for automatic correction]' && (
            <div className="px-4 pb-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                <Info size={12} />
                Suggested Correction
              </div>
              <pre className="code-block text-green-400 text-xs overflow-x-auto whitespace-pre-wrap">
                {issue.suggested_correction}
              </pre>
            </div>
          )}

          {/* Actions */}
          {issue.status === 'open' && (
            <div className="px-4 py-3 bg-surface-elevated/50 border-t border-surface-border flex items-center gap-3">
              <button
                onClick={() => updateStatus.mutate('approved')}
                disabled={updateStatus.isPending}
                className="flex items-center gap-2 px-3 py-1.5 bg-green-900/40 hover:bg-green-900/60 border border-green-800 text-green-300 rounded-md text-sm transition-colors"
              >
                <CheckCircle size={14} />
                Approve
              </button>
              <button
                onClick={() => updateStatus.mutate('rejected')}
                disabled={updateStatus.isPending}
                className="flex items-center gap-2 px-3 py-1.5 bg-red-900/40 hover:bg-red-900/60 border border-red-800 text-red-300 rounded-md text-sm transition-colors"
              >
                <XCircle size={14} />
                Reject
              </button>
            </div>
          )}

          {issue.status === 'approved' && (
            <div className="px-4 py-3 bg-surface-elevated/50 border-t border-surface-border flex items-center gap-3">
              <button
                onClick={() => applyPatch.mutate()}
                disabled={applyPatch.isPending}
                className="btn-primary flex items-center gap-2"
              >
                <CheckCircle size={14} />
                {applyPatch.isPending ? 'Applying…' : 'Apply Patch to File'}
              </button>
              <span className="text-xs text-gray-500">
                This will write the correction directly to the documentation file.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
