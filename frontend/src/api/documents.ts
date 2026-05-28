import type { AxiosProgressEvent, AxiosResponse } from 'axios'
import { calcHttpUploadPercent } from '../utils/kbUploadProgress'
import { http } from './http'

function formDataUploadBytes(formData: FormData): number {
  let sum = 0
  for (const value of formData.values()) {
    if (value instanceof File) sum += value.size
  }
  return sum
}

export type DocumentSummary = {
  id: string
  title: string
  status: string
  created_at: string
  updated_at?: string
  folder_id?: string | null
  /** 服务端归一化目录（如 `资料/2023`）；与 folder_id 对应的路径缓存 */
  folder_path?: string | null
}

export async function listKbDocuments(kbId: string): Promise<DocumentSummary[]> {
  const res = await http.get(`/api/v1/knowledge-bases/${kbId}/documents`)
  return (res.data?.data?.items || []) as DocumentSummary[]
}

export async function getDocument(docId: string) {
  return await http.get<{ data?: DocumentSummary }>(`/api/v1/documents/${docId}`)
}

export async function renameDocument(docId: string, title: string) {
  return await http.patch(`/api/v1/documents/${docId}`, { title })
}

export async function deleteDocument(docId: string) {
  return await http.delete(`/api/v1/documents/${docId}`)
}

export async function downloadDocumentBlob(docId: string) {
  return await http.get(`/api/v1/documents/${docId}/file`, { responseType: 'blob' })
}

export async function uploadDocument(
  formData: FormData,
  opts: {
    params: Record<string, string>
    onUploadProgress?: (pct: number) => void
    signal?: AbortSignal
  },
) {
  const fileSize = formDataUploadBytes(formData)
  const onUploadProgress = opts.onUploadProgress
    ? (evt: AxiosProgressEvent) => {
        opts.onUploadProgress?.(calcHttpUploadPercent(evt, fileSize))
      }
    : undefined

  return await http.post<unknown>('/api/v1/documents', formData, {
    params: opts.params,
    onUploadProgress,
    signal: opts.signal,
  })
}

/** 批量上传 PDF（multipart：多个 files 字段 + 可选 relative_paths 表单 JSON 数组） */
export async function uploadDocumentsBatch(
  kbId: string,
  formData: FormData,
  opts?: { params?: Record<string, string>; onUploadProgress?: (pct: number) => void },
) {
  const fileSize = formDataUploadBytes(formData)
  const onUploadProgress = opts?.onUploadProgress
    ? (evt: AxiosProgressEvent) => {
        opts?.onUploadProgress?.(calcHttpUploadPercent(evt, fileSize))
      }
    : undefined

  return await http.post<unknown>(`/api/v1/knowledge-bases/${kbId}/documents/batch`, formData, {
    params: opts?.params,
    onUploadProgress,
  })
}

export type ChatPostEnvelope = {
  data?: {
    answer?: string
    citations?: Array<unknown>
    conversation_id?: string
  }
}

export async function postChat(body: {
  kb_id: string
  question: string
  conversation_id?: string
  document_id?: string
  folder_id?: string
  chat_mode?: 'fast' | 'deep'
}): Promise<AxiosResponse<ChatPostEnvelope>> {
  return await http.post('/api/v1/chat', body)
}
