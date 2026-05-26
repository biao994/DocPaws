/** 浏览列表仅展示已可检索的文档 */
export function isReadyDocument(doc: { status: string }): boolean {
  return doc.status === 'ready'
}

/** 进页后需纳入进度面板的文档 */
export function isPendingUploadDocument(doc: { status: string }): boolean {
  return doc.status === 'draft' || doc.status === 'indexing' || doc.status === 'failed'
}

export type RestoreDocInput = {
  id: string
  title: string
  status: string
  folder_path?: string | null
}

export type RestoreJobInput = {
  id: string
  status?: string
  progress?: number
  error_message?: string | null
} | null

export type RestoreTaskDraft = {
  id: string
  fileName: string
  uploadProgress: number
  indexProgress: number
  status: 'indexing' | 'failed'
  documentId: string
  jobId?: string
  errorMessage?: string
}

/** 从文档 + 可选 index job 生成恢复用进度项 */
export function buildRestoreTaskFromDocument(
  doc: RestoreDocInput,
  job: RestoreJobInput,
): RestoreTaskDraft {
  const fileName = displayFileName(doc)
  const base = {
    id: `restore_${doc.id}`,
    fileName,
    uploadProgress: 100,
    documentId: doc.id,
  }

  if (doc.status === 'failed') {
    return {
      ...base,
      indexProgress: 100,
      status: 'failed',
      errorMessage: '异常',
    }
  }

  const jobStatus = job?.status
  const progress = typeof job?.progress === 'number' ? job.progress : 0
  if (jobStatus === 'failed') {
    return {
      ...base,
      jobId: job?.id,
      indexProgress: 100,
      status: 'failed',
      errorMessage: job?.error_message || '异常',
    }
  }

  return {
    ...base,
    jobId: job?.id,
    indexProgress: progress,
    status: 'indexing',
  }
}

export function displayFileName(doc: Pick<RestoreDocInput, 'title' | 'folder_path'>): string {
  const fp = (doc.folder_path ?? '').trim()
  if (fp) return doc.title
  const t = (doc.title || '').replace(/\\/g, '/')
  if (t.includes('/')) return t.split('/').pop() || doc.title
  return doc.title
}

/** 合并恢复任务，同 documentId 以 incoming 为准 */
export function mergeRestoreUploadTasks<T extends { documentId?: string }>(
  existing: T[],
  incoming: T[],
): T[] {
  const incomingDocIds = new Set(
    incoming.map((t) => t.documentId).filter((id): id is string => !!id),
  )
  const kept = existing.filter((t) => !t.documentId || !incomingDocIds.has(t.documentId))
  return [...kept, ...incoming]
}

export function uploadProgressStatusLabel(
  status: 'uploading' | 'indexing' | 'succeeded' | 'failed',
): string {
  if (status === 'uploading') return '上传中'
  if (status === 'indexing') return '处理中'
  if (status === 'succeeded') return '完成'
  return '异常'
}

export function canCancelUploadTask(status: 'uploading' | 'indexing' | 'succeeded' | 'failed'): boolean {
  return status === 'uploading' || status === 'indexing' || status === 'failed'
}

/** 合成进度：上传占 70%，建索引占 30% */
export function overallUploadPercent(uploadProgress: number, indexProgress: number): number {
  const uploadPart = Math.max(0, Math.min(100, uploadProgress))
  const indexPart = Math.max(0, Math.min(100, indexProgress))
  return Math.round(uploadPart * 0.7 + indexPart * 0.3)
}
