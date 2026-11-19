export interface Repository {
  id: string
  name: string
  url: string | null
  branch: string
  source: 'github' | 'zip' | 'local'
  index_status: 'pending' | 'indexing' | 'ready' | 'error'
  last_indexed_at: string | null
  head_commit: string | null
  error_message: string | null
  stats?: RepositoryStats
}

export interface RepositoryStats {
  symbols: number
  doc_sections: number
  open_drift_issues: number
  mappings: number
}

export interface DriftIssue {
  id: string
  repo_id: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  issue_type: 'outdated' | 'missing' | 'potentially_outdated'
  status: 'open' | 'approved' | 'rejected' | 'applied'
  description: string
  evidence_code: string
  evidence_doc: string
  doc_file_path: string
  doc_start_line: number
  code_file_path: string
  suggested_correction: string | null
  confidence: number
  commit_sha: string | null
  created_at: string
  resolved_at: string | null
  patches?: Patch[]
}

export interface Patch {
  id: string
  file_path: string
  original_text: string
  replacement_text: string
  start_line: number
  end_line: number
  applied_at: string | null
}

export interface CodeSymbol {
  id: string
  name: string
  qualified_name: string | null
  symbol_type: string
  file_path: string
  signature: string | null
  start_line: number
  end_line: number
}

export interface DocSection {
  id: string
  file_path: string
  heading: string | null
  section_type: string
  start_line: number
  end_line: number
  content_preview: string
}

export interface Mapping {
  id: string
  symbol_name: string
  symbol_type: string
  symbol_file: string
  doc_file: string
  doc_heading: string | null
  evidence_type: string
  evidence_detail: string
  confidence: number
}
