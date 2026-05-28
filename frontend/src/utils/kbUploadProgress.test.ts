import { describe, expect, it } from 'vitest'
import {
  buildRestoreTaskFromDocument,
  canCancelUploadTask,
  displayFileName,
  displayTaskPercent,
  INDEX_FAILURE_MESSAGE,
  uploadTaskStatusLabel,
  isPendingUploadDocument,
  isReadyDocument,
  mergeRestoreUploadTasks,
  uploadProgressStatusLabel,
} from './kbUploadProgress'

describe('isReadyDocument', () => {
  it('only ready passes', () => {
    expect(isReadyDocument({ status: 'ready' })).toBe(true)
    expect(isReadyDocument({ status: 'indexing' })).toBe(false)
    expect(isReadyDocument({ status: 'failed' })).toBe(false)
  })
})

describe('isPendingUploadDocument', () => {
  it('includes draft indexing failed', () => {
    expect(isPendingUploadDocument({ status: 'draft' })).toBe(true)
    expect(isPendingUploadDocument({ status: 'indexing' })).toBe(true)
    expect(isPendingUploadDocument({ status: 'failed' })).toBe(true)
    expect(isPendingUploadDocument({ status: 'ready' })).toBe(false)
  })
})

describe('buildRestoreTaskFromDocument', () => {
  it('failed doc becomes failed task without fake 100% index', () => {
    const t = buildRestoreTaskFromDocument(
      { id: 'd1', title: 'a.pdf', status: 'failed' },
      null,
    )
    expect(t.status).toBe('failed')
    expect(t.errorMessage).toBe(INDEX_FAILURE_MESSAGE)
    expect(t.uploadProgress).toBe(100)
    expect(t.indexProgress).toBe(0)
  })

  it('indexing doc uses job progress', () => {
    const t = buildRestoreTaskFromDocument(
      { id: 'd2', title: 'b.pdf', status: 'indexing', folder_path: 'dir' },
      { id: 'j1', status: 'running', progress: 42 },
    )
    expect(t.status).toBe('indexing')
    expect(t.jobId).toBe('j1')
    expect(t.indexProgress).toBe(42)
    expect(t.fileName).toBe('b.pdf')
  })

  it('indexing doc with failed job stays indexing', () => {
    const t = buildRestoreTaskFromDocument(
      { id: 'd3', title: 'c.pdf', status: 'indexing' },
      { id: 'j2', status: 'failed', progress: 80 },
    )
    expect(t.status).toBe('indexing')
    expect(t.indexProgress).toBe(80)
  })
})

describe('displayFileName', () => {
  it('uses basename for legacy path title', () => {
    expect(displayFileName({ title: '资料/报告.pdf', folder_path: null })).toBe('报告.pdf')
  })
})

describe('mergeRestoreUploadTasks', () => {
  it('replaces same documentId', () => {
    const merged = mergeRestoreUploadTasks(
      [{ id: 'a', documentId: 'd1' }],
      [{ id: 'b', documentId: 'd1' }],
    )
    expect(merged).toHaveLength(1)
    expect(merged[0].id).toBe('b')
  })
})

describe('displayTaskPercent', () => {
  it('uses upload progress while uploading', () => {
    expect(
      displayTaskPercent({ status: 'uploading', uploadProgress: 55, indexProgress: 0 }),
    ).toBe(55)
  })

  it('uses index progress after upload', () => {
    expect(
      displayTaskPercent({ status: 'indexing', uploadProgress: 100, indexProgress: 42 }),
    ).toBe(42)
  })

  it('uses index progress when job already running but status not flipped', () => {
    expect(
      displayTaskPercent({
        status: 'uploading',
        uploadProgress: 0,
        indexProgress: 50,
        jobId: 'j1',
      }),
    ).toBe(50)
  })

  it('caps failed at 99 when index was 100', () => {
    expect(
      displayTaskPercent({ status: 'failed', uploadProgress: 100, indexProgress: 100 }),
    ).toBe(99)
  })
})

describe('uploadTaskStatusLabel', () => {
  it('shows 处理中 when index progress is available', () => {
    expect(
      uploadTaskStatusLabel({
        status: 'uploading',
        uploadProgress: 0,
        indexProgress: 50,
        jobId: 'j1',
      }),
    ).toBe('处理中')
  })
})

describe('uploadProgressStatusLabel', () => {
  it('failed shows 处理失败', () => {
    expect(uploadProgressStatusLabel('failed')).toBe(INDEX_FAILURE_MESSAGE)
  })
})

describe('canCancelUploadTask', () => {
  it('allows cancel for active and failed', () => {
    expect(canCancelUploadTask('uploading')).toBe(true)
    expect(canCancelUploadTask('failed')).toBe(true)
    expect(canCancelUploadTask('succeeded')).toBe(false)
  })
})
