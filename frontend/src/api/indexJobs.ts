import { http } from './http'

export type IndexJobSummary = {
  id: string
  kb_id?: string
  status: string
  progress: number
  error_message?: string | null
}

/** 从 API 响应体解析 IndexJob（兼容 axios 的 data 包装） */
export function unwrapIndexJobPayload(body: unknown): IndexJobSummary | null {
  if (!body || typeof body !== 'object') return null
  const root = body as Record<string, unknown>
  const data = root.data
  if (data && typeof data === 'object') {
    return data as IndexJobSummary
  }
  if (typeof root.id === 'string' && typeof root.status === 'string') {
    return root as IndexJobSummary
  }
  return null
}

export function parseIndexJobProgress(progress: unknown): number {
  if (typeof progress === 'number' && Number.isFinite(progress)) {
    return Math.max(0, Math.min(100, Math.round(progress)))
  }
  if (typeof progress === 'string' && progress.trim() !== '') {
    const n = Number(progress)
    if (Number.isFinite(n)) return Math.max(0, Math.min(100, Math.round(n)))
  }
  return 0
}

export async function getIndexJob(jobId: string) {
  return await http.get<{ data?: IndexJobSummary }>(`/api/v1/index-jobs/${jobId}`)
}

export async function getDocumentIndexJob(documentId: string) {
  return await http.get<{ data?: IndexJobSummary }>(
    `/api/v1/index-jobs/documents/${documentId}/index-job`,
  )
}
