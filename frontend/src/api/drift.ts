import api from './client'
import type { DriftIssue } from '../types'

export const driftApi = {
  list: (params?: { repo_id?: string; status?: string; severity?: string }) =>
    api.get<DriftIssue[]>('/drift', { params }).then(r => r.data),

  get: (id: string) => api.get<DriftIssue>(`/drift/${id}`).then(r => r.data),

  updateStatus: (id: string, status: string) =>
    api.patch<DriftIssue>(`/drift/${id}/status`, { status }).then(r => r.data),

  applyPatch: (id: string) =>
    api.post(`/drift/${id}/apply`).then(r => r.data),

  getDiff: (id: string) =>
    api.get(`/drift/${id}/diff`).then(r => r.data),

  analyzeFiles: (
    repoId: string,
    files: { path: string; old_content?: string; new_content?: string }[],
    docFilePath: string,
  ) =>
    api.post(`/analysis/${repoId}/files`, {
      files,
      doc_file_path: docFilePath,
    }).then(r => r.data),
}
