import { parseIndexJobProgress } from '../api/indexJobs'

/** 浏览列表仅展示已可检索的文档 */
export function isReadyDocument(doc: { status: string }): boolean {
  return doc.status === 'ready'
}

/** 进页后需纳入进度面板的文档 */
export function isPendingUploadDocument(doc: { status: string }): boolean {
  return doc.status === 'draft' || doc.status === 'indexing' || doc.status === 'failed'
}

export const INDEX_FAILURE_MESSAGE = '处理失败'

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

function clampPercent(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)))
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
      indexProgress: 0,
      status: 'failed',
      errorMessage: INDEX_FAILURE_MESSAGE,
    }
  }

  const jobStatus = job?.status
  const progress = parseIndexJobProgress(job?.progress)

  // Job 失败但文档仍在处理：以文档为准，继续轮询
  if (jobStatus === 'failed' && (doc.status === 'indexing' || doc.status === 'draft')) {
    return {
      ...base,
      jobId: job?.id,
      indexProgress: progress,
      status: 'indexing',
    }
  }

  if (jobStatus === 'failed') {
    return {
      ...base,
      jobId: job?.id,
      indexProgress: progress,
      status: 'failed',
      errorMessage: INDEX_FAILURE_MESSAGE,
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

export type UploadProgressTaskView = {
  status: 'uploading' | 'indexing' | 'succeeded' | 'failed'
  uploadProgress: number
  indexProgress: number
  jobId?: string
  documentId?: string
}

/** 是否仍处于 HTTP 上传阶段（未拿到 job 且字节未传完） */
export function isHttpUploadPhase(task: UploadProgressTaskView): boolean {
  return (
    task.status === 'uploading' &&
    task.uploadProgress < 100 &&
    task.indexProgress <= 0 &&
    !task.jobId &&
    !task.documentId
  )
}

export function uploadTaskStatusLabel(task: UploadProgressTaskView): string {
  if (task.status === 'failed') return INDEX_FAILURE_MESSAGE
  if (task.status === 'succeeded') return '完成'
  if (isHttpUploadPhase(task)) return '上传中'
  return '处理中'
}

export function uploadProgressStatusLabel(
  status: 'uploading' | 'indexing' | 'succeeded' | 'failed',
): string {
  if (status === 'uploading') return '上传中'
  if (status === 'indexing') return '处理中'
  if (status === 'succeeded') return '完成'
  return INDEX_FAILURE_MESSAGE
}

export function canCancelUploadTask(status: 'uploading' | 'indexing' | 'succeeded' | 'failed'): boolean {
  return status === 'uploading' || status === 'indexing' || status === 'failed'
}

/** 上传字节阶段用 uploadProgress；一旦进入索引（有 job/索引进度）用 indexProgress */
export function displayTaskPercent(task: UploadProgressTaskView): number {
  if (isHttpUploadPhase(task)) {
    return clampPercent(task.uploadProgress)
  }
  const raw = clampPercent(task.indexProgress)
  if (task.status === 'failed' && raw >= 100) return 99
  return raw
}

/** axios 上传进度：total 缺失时用 file.size 估算 */
export function calcHttpUploadPercent(
  evt: { loaded?: number; total?: number },
  fileSize: number,
): number {
  const loaded = evt.loaded ?? 0
  const total =
    evt.total && evt.total > 0 ? evt.total : fileSize > 0 ? fileSize : 0
  if (total <= 0) return loaded > 0 ? 99 : 0
  return Math.min(100, Math.round((loaded / total) * 100))
}

/** @deprecated 使用 displayTaskPercent */
export function overallUploadPercent(uploadProgress: number, indexProgress: number): number {
  return displayTaskPercent({
    status: uploadProgress < 100 ? 'uploading' : 'indexing',
    uploadProgress,
    indexProgress,
  })
}
