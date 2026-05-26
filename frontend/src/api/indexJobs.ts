import { http } from './http'

export type IndexJobSummary = {
  id: string
  kb_id?: string
  status: string
  progress: number
  error_message?: string | null
}

export async function getIndexJob(jobId: string) {
  return await http.get<{ data?: IndexJobSummary }>(`/api/v1/index-jobs/${jobId}`)
}

export async function getDocumentIndexJob(documentId: string) {
  return await http.get<{ data?: IndexJobSummary }>(
    `/api/v1/index-jobs/documents/${documentId}/index-job`,
  )
}
