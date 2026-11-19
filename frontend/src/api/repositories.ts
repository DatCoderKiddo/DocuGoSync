import api from './client'
import type { Repository, CodeSymbol, DocSection, Mapping } from '../types'

export const repositoriesApi = {
  list: () => api.get<Repository[]>('/repositories').then(r => r.data),

  get: (id: string) => api.get<Repository>(`/repositories/${id}`).then(r => r.data),

  connect: (url: string, branch: string) =>
    api.post<Repository>('/repositories', { url, branch }).then(r => r.data),

  uploadZip: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<Repository>('/repositories/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  delete: (id: string) => api.delete(`/repositories/${id}`),

  reindex: (id: string) => api.post(`/repositories/${id}/reindex`),

  getSymbols: (id: string) =>
    api.get<CodeSymbol[]>(`/repositories/${id}/symbols`).then(r => r.data),

  getDocs: (id: string) =>
    api.get<DocSection[]>(`/repositories/${id}/docs`).then(r => r.data),

  getMappings: (id: string) =>
    api.get<Mapping[]>(`/repositories/${id}/mappings`).then(r => r.data),
}
