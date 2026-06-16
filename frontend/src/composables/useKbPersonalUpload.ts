import { ref, type Ref, onScopeDispose } from 'vue'
import axios, { isAxiosError, type AxiosProgressEvent } from 'axios'
import {
  getDocumentIndexJob,
  getIndexJob,
  parseIndexJobProgress,
  unwrapIndexJobPayload,
  type IndexJobSummary,
} from '../api/indexJobs'
import {
  deleteDocument,
  getDocument,
  uploadDocument,
  uploadDocumentsBatch,
  type DocumentSummary,
} from '../api/documents'
import { API_BASE_URL, withApiBase } from '../api/config'
import {
  buildRestoreTaskFromDocument,
  calcHttpUploadPercent,
  INDEX_FAILURE_MESSAGE,
  isPendingUploadDocument,
  mergeRestoreUploadTasks,
} from '../utils/kbUploadProgress'
import { ErrorCode } from '../utils/errors'

export type KbUploadTarget = { id: string }

export type UploadTaskStatus = 'uploading' | 'indexing' | 'succeeded' | 'failed'

export type UploadTask = {
  id: string
  fileName: string
  uploadProgress: number
  indexProgress: number
  /** 同一次上传重试复用，对应后端 idempotency_key */
  idempotencyKey: string
  jobId?: string
  documentId?: string
  status: UploadTaskStatus
  errorMessage?: string
}

function newUploadIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `upload_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

type ApiErrorPayload = {
  error_code?: string
  message?: string
  user_hint?: string
  details?: {
    existing_document_id?: string
    existing_title?: string
    incoming_filename?: string
  }
}

function getApiErrorPayload(err: unknown): ApiErrorPayload | undefined {
  if (!isAxiosError(err) || err.response?.data == null) return undefined
  const data = err.response.data
  if (typeof data !== 'object' || data === null) return undefined
  const rec = data as Record<string, unknown>
  if (typeof rec.error_code === 'string') {
    return data as ApiErrorPayload
  }
  const inner = rec.detail
  if (inner && typeof inner === 'object' && inner !== null && 'error_code' in inner) {
    return inner as ApiErrorPayload
  }
  return undefined
}

function getApiErrorMessage(err: unknown): string {
  const p = getApiErrorPayload(err)
  if (p?.message) return p.message
  if (isAxiosError(err) && err.response?.data && typeof err.response.data === 'object') {
    const d = err.response.data as { message?: string }
    if (typeof d.message === 'string') return d.message
  }
  return (err as Error)?.message || '请求失败'
}

/** 后端 KB 调度被 stale 清理作废；对用户仍可能由后续任务索引成功 */
function isStaleIndexJobError(message?: string | null): boolean {
  return typeof message === 'string' && message.includes('stale:')
}

function isPdfFile(file: File) {
  const byName = file.name.toLowerCase().endsWith('.pdf')
  const type = (file.type || '').toLowerCase()
  const byType = type === 'application/pdf' || type === 'application/x-pdf'
  return byName || byType
}

function folderDisplayNameFromFiles(files: File[]): string {
  for (const f of files) {
    const wp = (f as File & { webkitRelativePath?: string }).webkitRelativePath
    if (!wp) continue
    const first = wp.replace(/\\/g, '/').split('/').filter(Boolean)[0]
    if (first) return first
  }
  return '文件夹'
}

/** 与后端单文件 auto_rename 一致：yyyyMMddHHmmss */
function uploadTimestampSuffix(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

/** 将 relative_paths 中的上传根文件夹名改为带时间戳的新名称 */
function renameUploadFolderInRelativePaths(
  relPaths: string[],
  folderName: string,
  renamedFolder: string,
  kbFolderPrefix: string,
): string[] {
  const prefixDepth = kbFolderPrefix ? kbFolderPrefix.split('/').filter(Boolean).length : 0
  return relPaths.map((rel) => {
    const parts = rel.replace(/\\/g, '/').split('/').filter(Boolean)
    if (parts[prefixDepth] === folderName) {
      parts[prefixDepth] = renamedFolder
    }
    return parts.join('/')
  })
}

export type NameConflictPrompt = {
  file: File
  existingDocumentId: string
  displayName: string
  allowReplace: boolean
  /** 文件夹批量上传：仅保留全部，整夹重命名后落入新目录 */
  scope?: 'file' | 'folder'
}

export function useKbPersonalUpload(opts: {
  uploadFolderId: Ref<string | null>
  /** 批量上传时拼 relative_paths 前缀；由选中文件夹的 path 推导 */
  uploadFolderPath: Ref<string | null>
  showNameConflictModal: Ref<boolean>
  ensureSelectedKb: () => Promise<KbUploadTarget | null>
  reloadDocuments: () => void | Promise<void>
  promptNameConflict: (p: NameConflictPrompt) => Promise<'replace' | 'auto_rename' | 'cancel'>
}) {
  const uploadTasks = ref<UploadTask[]>([])
  const uploadProgressPanelOpen = ref(false)
  const uploadAbortControllers = new Map<string, AbortController>()
  let indexPollingTimer: number | null = null
  let indexPollingInFlight = false
  let refreshTimer: number | null = null

  const disposeTimers = () => {
    if (indexPollingTimer != null) {
      window.clearInterval(indexPollingTimer)
      indexPollingTimer = null
    }
    if (refreshTimer != null) {
      window.clearTimeout(refreshTimer)
      refreshTimer = null
    }
  }

  onScopeDispose(disposeTimers)

  const scheduleReloadDocuments = () => {
    if (refreshTimer != null) window.clearTimeout(refreshTimer)
    refreshTimer = window.setTimeout(() => {
      refreshTimer = null
      void opts.reloadDocuments()
    }, 600)
  }

  const clearFinishedUploadTasks = () => {
    uploadTasks.value = uploadTasks.value.filter((t) => t.status !== 'succeeded')
  }

  const openUploadProgressPanel = () => {
    uploadProgressPanelOpen.value = true
  }

  const closeUploadProgressPanel = () => {
    uploadProgressPanelOpen.value = false
    clearFinishedUploadTasks()
  }

  const dismissSucceededTask = (task: UploadTask) => {
    if (task.status !== 'succeeded') return
    uploadTasks.value = uploadTasks.value.filter((t) => t.id !== task.id)
  }

  const markTaskSucceeded = (task: UploadTask) => {
    task.status = 'succeeded'
    task.uploadProgress = 100
    task.indexProgress = 100
    task.errorMessage = undefined
    scheduleReloadDocuments()
    dismissSucceededTask(task)
  }

  const markTaskFailed = (task: UploadTask, message = INDEX_FAILURE_MESSAGE) => {
    task.status = 'failed'
    task.errorMessage = message
    scheduleReloadDocuments()
  }

  type DocFinalizeOutcome = 'ready' | 'failed' | 'pending'

  /** 以文档状态为准收尾，避免「Job 成功但文档 failed」等误报 */
  const finalizeFromDocument = async (task: UploadTask): Promise<DocFinalizeOutcome> => {
    if (!task.documentId) return 'pending'
    try {
      const res = await getDocument(task.documentId)
      const doc = res.data?.data
      const st = doc?.status
      if (st === 'ready') {
        markTaskSucceeded(task)
        return 'ready'
      }
      if (st === 'failed') {
        markTaskFailed(task)
        return 'failed'
      }
    } catch {
      // ignore
    }
    return 'pending'
  }

  const fetchIndexJobForTask = async (task: UploadTask): Promise<IndexJobSummary | null> => {
    try {
      if (task.jobId) {
        const res = await getIndexJob(task.jobId)
        return unwrapIndexJobPayload(res.data) ?? null
      }
      if (task.documentId) {
        const res = await getDocumentIndexJob(task.documentId)
        const job = unwrapIndexJobPayload(res.data)
        if (job?.id) task.jobId = job.id
        return job
      }
    } catch {
      // ignore
    }
    return null
  }

  const enterIndexProcessingPhase = (task: UploadTask, progress: number) => {
    if (task.uploadProgress < 100) task.uploadProgress = 100
    task.indexProgress = progress
    if (task.status === 'uploading') task.status = 'indexing'
  }

  const isActiveIndexPollTask = (t: UploadTask) => {
    if (t.status === 'indexing') return !!t.jobId || !!t.documentId
    if (t.status === 'uploading') {
      return !!t.jobId || !!t.documentId || t.uploadProgress >= 100 || t.indexProgress > 0
    }
    return false
  }

  const applyIndexJobSnapshot = async (task: UploadTask, job: IndexJobSummary) => {
    const st = job.status
    const progress = parseIndexJobProgress(job.progress)

    if (st === 'failed') {
      const errMsg = job.error_message
      if (isStaleIndexJobError(errMsg)) {
        task.errorMessage = undefined
        const outcome = await finalizeFromDocument(task)
        if (outcome !== 'pending') return
        return
      }
      const outcome = await finalizeFromDocument(task)
      if (outcome !== 'pending') return
      markTaskFailed(task)
      return
    }

    if (st === 'succeeded') {
      const outcome = await finalizeFromDocument(task)
      if (outcome === 'ready' || outcome === 'failed') return
      enterIndexProcessingPhase(task, progress)
      return
    }

    // queued / running：跟随后端 job.progress
    enterIndexProcessingPhase(task, progress)
  }

  const pollIndexJobsOnce = async () => {
    if (indexPollingInFlight) return
    indexPollingInFlight = true
    try {
      const activeTasks = uploadTasks.value.filter(isActiveIndexPollTask)
      if (activeTasks.length === 0) {
        if (indexPollingTimer != null) {
          window.clearInterval(indexPollingTimer)
          indexPollingTimer = null
        }
        return
      }

      for (const t of activeTasks) {
        if (!t.jobId && !t.documentId) continue

        const job = await fetchIndexJobForTask(t)
        if (job) {
          await applyIndexJobSnapshot(t, job)
          continue
        }

        if (t.documentId) {
          const outcome = await finalizeFromDocument(t)
          if (outcome !== 'pending') continue
        }
      }
    } finally {
      indexPollingInFlight = false
    }
  }

  const ensureIndexPolling = () => {
    const hasActive = uploadTasks.value.some(isActiveIndexPollTask)
    if (!hasActive) return

    void pollIndexJobsOnce()

    if (indexPollingTimer != null) return

    indexPollingTimer = window.setInterval(() => {
      void pollIndexJobsOnce()
    }, 1000)
  }

  const postDocumentUpload = async (
    file: File,
    kb: KbUploadTarget,
    conflictOpts: {
      on_conflict: 'create' | 'replace' | 'auto_rename'
      replace_document_id?: string
      folder_path?: string
      folder_id?: string
    },
    idempotencyKey: string,
    onUploadProgress?: (percent: number) => void,
    abortSignal?: AbortSignal,
  ) => {
    const formData = new FormData()
    formData.append('file', file)
    const params: Record<string, string> = {
      kb_id: kb.id,
      on_conflict: conflictOpts.on_conflict,
      idempotency_key: idempotencyKey,
    }
    if (conflictOpts.folder_id) {
      params.folder_id = conflictOpts.folder_id
    } else if (opts.uploadFolderId.value) {
      params.folder_id = opts.uploadFolderId.value
    } else if (conflictOpts.folder_path != null) {
      params.folder_path = conflictOpts.folder_path
    } else if (opts.uploadFolderPath.value) {
      params.folder_path = opts.uploadFolderPath.value
    }
    if (conflictOpts.replace_document_id) params.replace_document_id = conflictOpts.replace_document_id

    try {
      return await uploadDocument(formData, { params, onUploadProgress, signal: abortSignal })
    } catch (proxyError) {
      if (isAxiosError(proxyError) && proxyError.response) {
        throw proxyError
      }
      if (!API_BASE_URL) {
        throw proxyError
      }
      console.warn('[upload] proxy path failed, retry direct api base:', API_BASE_URL, proxyError)

      const handleDirectProgress = onUploadProgress
        ? (evt: AxiosProgressEvent) => {
            onUploadProgress(calcHttpUploadPercent(evt, file.size))
          }
        : undefined

      return await axios.post(withApiBase('/api/v1/documents'), formData, {
        params,
        signal: abortSignal,
        ...(handleDirectProgress ? { onUploadProgress: handleDirectProgress } : {}),
      })
    }
  }

  const removeUploadAbortController = (taskId: string) => {
    uploadAbortControllers.delete(taskId)
  }

  const bindUploadAbortController = (taskId: string): AbortSignal => {
    const prev = uploadAbortControllers.get(taskId)
    if (prev) prev.abort()
    const ctrl = new AbortController()
    uploadAbortControllers.set(taskId, ctrl)
    return ctrl.signal
  }

  const uploadDocumentWithProgress = async (
    file: File,
    kb: KbUploadTarget,
    conflictOpts: {
      on_conflict: 'create' | 'replace' | 'auto_rename'
      replace_document_id?: string
      folder_path?: string
      folder_id?: string
    },
    reuseTask?: UploadTask,
  ) => {
    const task: UploadTask =
      reuseTask ??
      ({
        id: `u_${Date.now()}_${Math.random().toString(16).slice(2)}`,
        fileName: file.name,
        uploadProgress: 0,
        indexProgress: 0,
        idempotencyKey: newUploadIdempotencyKey(),
        status: 'uploading',
      } as UploadTask)
    if (!reuseTask) {
      uploadTasks.value = [...uploadTasks.value, task]
      openUploadProgressPanel()
    }

    const abortSignal = bindUploadAbortController(task.id)
    try {
      const res = await postDocumentUpload(
        file,
        kb,
        conflictOpts,
        task.idempotencyKey,
        (p) => {
          task.uploadProgress = p
          if (p >= 100 && task.status === 'uploading') {
            task.status = 'indexing'
            ensureIndexPolling()
          }
        },
        abortSignal,
      )

      removeUploadAbortController(task.id)
      task.uploadProgress = 100
      const payload = res.data?.data
      task.documentId = payload?.document_id
      task.jobId = payload?.job_id
      task.status = 'indexing'

      ensureIndexPolling()
      await pollIndexJobsOnce()
      return payload
    } catch (e) {
      removeUploadAbortController(task.id)
      if (isAxiosError(e) && (e.code === 'ERR_CANCELED' || e.message === 'canceled')) {
        uploadTasks.value = uploadTasks.value.filter((x) => x.id !== task.id)
        return undefined
      }
      const body = getApiErrorPayload(e)
      if (body?.error_code === ErrorCode.NAME_CONFLICT) {
        if (!reuseTask) {
          uploadTasks.value = uploadTasks.value.filter((x) => x.id !== task.id)
        }
        throw e
      }

      task.status = 'failed'
      task.indexProgress = 0
      task.errorMessage = getApiErrorMessage(e)
      throw e
    }
  }

  const isNameConflictError = (err: unknown): boolean => {
    if (!isAxiosError(err)) return false
    if (err.response?.status !== 409) return false
    const body = getApiErrorPayload(err)
    return body?.error_code === ErrorCode.NAME_CONFLICT
  }

  const uploadWithConflictFlow = async (
    file: File,
    kb: KbUploadTarget,
    folderOpts?: { folder_id?: string; folder_path?: string },
    allowReplace = true,
    reuseTask?: UploadTask,
  ) => {
    const baseOpts = { on_conflict: 'create' as const, ...folderOpts }
    try {
      return await uploadDocumentWithProgress(file, kb, baseOpts, reuseTask)
    } catch (err) {
      if (!isNameConflictError(err)) throw err
      const body = getApiErrorPayload(err)
      const existingDocId = body?.details?.existing_document_id
      if (!existingDocId) throw err

      const displayName = body?.details?.incoming_filename || file.name
      const action = await opts.promptNameConflict({
        file,
        existingDocumentId: existingDocId,
        displayName,
        allowReplace,
      })
      if (action === 'cancel') return null
      if (action === 'replace' && allowReplace) {
        return await uploadDocumentWithProgress(
          file,
          kb,
          {
            on_conflict: 'replace',
            replace_document_id: existingDocId,
            ...folderOpts,
          },
          reuseTask,
        )
      }
      return await uploadDocumentWithProgress(
        file,
        kb,
        {
          on_conflict: 'auto_rename',
          ...folderOpts,
        },
        reuseTask,
      )
    }
  }

  const postFolderBatchUpload = async (
    kb: KbUploadTarget,
    formData: FormData,
    params: Record<string, string>,
    onUploadProgress?: (percent: number) => void,
  ) => {
    try {
      return await uploadDocumentsBatch(kb.id, formData, { params, onUploadProgress })
    } catch (proxyError) {
      if (isAxiosError(proxyError) && proxyError.response) {
        throw proxyError
      }
      if (!API_BASE_URL) {
        throw proxyError
      }
      console.warn('[upload] batch proxy failed, retry direct api base:', API_BASE_URL, proxyError)
      let batchBytes = 0
      for (const v of formData.values()) {
        if (v instanceof File) batchBytes += v.size
      }
      const handleDirectProgress = onUploadProgress
        ? (evt: AxiosProgressEvent) => {
            onUploadProgress(calcHttpUploadPercent(evt, batchBytes))
          }
        : undefined
      return await axios.post(
        withApiBase(`/api/v1/knowledge-bases/${kb.id}/documents/batch`),
        formData,
        {
          params,
          ...(handleDirectProgress ? { onUploadProgress: handleDirectProgress } : {}),
        },
      )
    }
  }

  const handlePdfFileChange = async (e: Event) => {
    const input = e.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    console.log('[upload] file selected:', file.name, file.size)
    try {
      const kb = await opts.ensureSelectedKb()
      if (!kb) {
        alert('请先在左侧选择一个知识库')
        return
      }
      const folderOpts = opts.uploadFolderId.value
        ? { folder_id: opts.uploadFolderId.value }
        : undefined
      await uploadWithConflictFlow(file, kb, folderOpts, true)
    } catch (error) {
      console.error('Upload failed:', error)
      alert(`上传失败：${getApiErrorMessage(error)}`)
    } finally {
      if (!opts.showNameConflictModal.value) input.value = ''
    }
  }

  const handlePdfFolderChange = async (e: Event) => {
    const input = e.target as HTMLInputElement
    const files = Array.from(input.files || [])
    if (files.length === 0) return

    try {
      const kb = await opts.ensureSelectedKb()
      if (!kb) {
        alert('请先在左侧选择一个知识库')
        input.value = ''
        return
      }

      let skipped = 0

      const pdfItems = files
        .filter((f) => {
          if (!isPdfFile(f)) {
            skipped += 1
            return false
          }
          return true
        })
        .map((f) => ({ file: f }))

      if (pdfItems.length === 0) {
        await opts.reloadDocuments()
        if (skipped > 0) {
          alert(`文件夹内未检测到可上传的 PDF（共跳过 ${skipped} 个）`)
        }
        return
      }

      const esc = (s: string) => s.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
      const prefix = opts.uploadFolderPath.value ? esc(opts.uploadFolderPath.value) : ''

      const relativePaths = pdfItems.map(({ file }) => {
        const wp = ((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name).replace(
          /\\/g,
          '/',
        )
        if (!prefix) return wp
        return `${prefix}/${wp}`.replace(/\/+/g, '/')
      })

      const folderLabel = folderDisplayNameFromFiles(pdfItems.map((x) => x.file))

      const task: UploadTask = {
        id: `batch_${Date.now()}_${Math.random().toString(16).slice(2)}`,
        fileName: `${folderLabel}`,
        uploadProgress: 0,
        indexProgress: 0,
        idempotencyKey: newUploadIdempotencyKey(),
        status: 'uploading',
      }
      uploadTasks.value = [...uploadTasks.value, task]
      openUploadProgressPanel()

      type BatchPayload = {
        job_id?: string
        items?: Array<{ document_id?: string }>
      }

      const applyBatchResultToTask = async (res: { data?: { data?: BatchPayload } }) => {
        task.uploadProgress = 100
        const payload = res.data?.data
        task.jobId = payload?.job_id
        const firstId = payload?.items?.[0]?.document_id
        task.documentId = firstId
        if (payload?.job_id) {
          task.status = 'indexing'
          ensureIndexPolling()
          await pollIndexJobsOnce()
        } else {
          markTaskSucceeded(task)
        }
      }

      const buildFolderBatchFormData = (relPaths: string[], fls: File[]) => {
        const fd = new FormData()
        for (const f of fls) fd.append('files', f)
        fd.append('relative_paths', JSON.stringify(relPaths))
        return fd
      }

      let pendingFiles = pdfItems.map((x) => x.file)
      let pendingRel = relativePaths.slice()
      let guard = 0

      try {
        folderLoop: while (pendingFiles.length > 0 && guard < 500) {
          guard += 1
          task.status = 'uploading'
          try {
            const batchParams: Record<string, string> = {
              on_conflict: 'create',
              idempotency_key: task.idempotencyKey,
            }
            if (opts.uploadFolderId.value && !prefix) {
              batchParams.folder_id = opts.uploadFolderId.value
            }
            const res = await postFolderBatchUpload(
              kb,
              buildFolderBatchFormData(pendingRel, pendingFiles),
              batchParams,
              (p) => {
                task.uploadProgress = p
                if (p >= 100 && task.status === 'uploading') {
                  task.status = 'indexing'
                  ensureIndexPolling()
                }
              },
            )
            await applyBatchResultToTask(res)
            break folderLoop
          } catch (error) {
            if (!isNameConflictError(error)) {
              task.status = 'failed'
              task.uploadProgress = 0
              task.errorMessage = getApiErrorMessage(error)
              console.error('Folder batch upload failed:', error)
              alert(`文件夹上传失败：${task.errorMessage}`)
              break folderLoop
            }
            const body = getApiErrorPayload(error)
            if (!body?.details?.existing_document_id) {
              task.status = 'failed'
              task.uploadProgress = 0
              task.errorMessage = getApiErrorMessage(error)
              alert(`文件夹上传失败：${task.errorMessage}`)
              break folderLoop
            }
            const action = await opts.promptNameConflict({
              file: pendingFiles[0],
              existingDocumentId: body.details.existing_document_id,
              displayName: folderLabel,
              allowReplace: false,
              scope: 'folder',
            })
            if (action === 'cancel') {
              task.status = 'failed'
              task.errorMessage = '已取消'
              break folderLoop
            }
            const renamedFolder = `${folderLabel}_${uploadTimestampSuffix()}`
            pendingRel = renameUploadFolderInRelativePaths(pendingRel, folderLabel, renamedFolder, prefix)
            task.fileName = renamedFolder
            continue folderLoop
          }
        }
        if (guard >= 500 && task.status === 'uploading') {
          task.status = 'failed'
          task.errorMessage = '上传处理次数过多，请稍后重试'
        }
      } catch (error) {
        task.status = 'failed'
        task.uploadProgress = 0
        task.errorMessage = getApiErrorMessage(error)
        console.error('Folder batch upload failed:', error)
        alert(`文件夹上传失败：${task.errorMessage}`)
      }

      if (skipped > 0 && task.status !== 'failed') {
        console.info(`[upload] skipped ${skipped} non-PDF files in folder`)
      }
    } finally {
      input.value = ''
    }
  }

  const restorePendingUploadTasks = async (allDocs: DocumentSummary[]) => {
    const pending = allDocs.filter(isPendingUploadDocument)
    if (pending.length === 0) return

    const restored: UploadTask[] = []
    for (const doc of pending) {
      let job = null
      if (doc.status !== 'failed') {
        try {
          const res = await getDocumentIndexJob(doc.id)
          job = res.data?.data ?? null
        } catch {
          job = null
        }
      }
      const draft = buildRestoreTaskFromDocument(doc, job)
      restored.push({
        ...draft,
        idempotencyKey: `restore_${doc.id}`,
        status: draft.status,
      })
    }

    uploadTasks.value = mergeRestoreUploadTasks(uploadTasks.value, restored)
    if (restored.some((t) => t.status === 'indexing')) {
      ensureIndexPolling()
    }
    if (restored.length > 0) {
      openUploadProgressPanel()
    }
  }

  const cancelUploadTask = async (task: UploadTask) => {
    const ctrl = uploadAbortControllers.get(task.id)
    if (ctrl) {
      ctrl.abort()
      removeUploadAbortController(task.id)
    }
    if (task.documentId) {
      try {
        await deleteDocument(task.documentId)
      } catch {
        // ignore
      }
    }
    uploadTasks.value = uploadTasks.value.filter((t) => t.id !== task.id)
    const hasActive = uploadTasks.value.some(isActiveIndexPollTask)
    if (!hasActive && indexPollingTimer != null) {
      window.clearInterval(indexPollingTimer)
      indexPollingTimer = null
    }
  }

  return {
    uploadTasks,
    uploadProgressPanelOpen,
    closeUploadProgressPanel,
    handlePdfFileChange,
    handlePdfFolderChange,
    restorePendingUploadTasks,
    cancelUploadTask,
  }
}
