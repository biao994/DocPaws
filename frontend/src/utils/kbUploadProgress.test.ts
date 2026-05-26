import { describe, expect, it } from 'vitest'
import {
  buildRestoreTaskFromDocument,
  canCancelUploadTask,
  displayFileName,
  isPendingUploadDocument,
  isReadyDocument,
  mergeRestoreUploadTasks,
  overallUploadPercent,
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
  it('failed doc becomes failed task with 异常', () => {
    const t = buildRestoreTaskFromDocument(
      { id: 'd1', title: 'a.pdf', status: 'failed' },
      null,
    )
    expect(t.status).toBe('failed')
    expect(t.errorMessage).toBe('异常')
    expect(t.uploadProgress).toBe(100)
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

describe('overallUploadPercent', () => {
  it('weights upload 70% and index 30%', () => {
    expect(overallUploadPercent(100, 100)).toBe(100)
    expect(overallUploadPercent(100, 0)).toBe(70)
    expect(overallUploadPercent(0, 100)).toBe(30)
  })
})

describe('uploadProgressStatusLabel', () => {
  it('failed shows 异常', () => {
    expect(uploadProgressStatusLabel('failed')).toBe('异常')
  })
})

describe('canCancelUploadTask', () => {
  it('allows cancel for active and failed', () => {
    expect(canCancelUploadTask('uploading')).toBe(true)
    expect(canCancelUploadTask('failed')).toBe(true)
    expect(canCancelUploadTask('succeeded')).toBe(false)
  })
})
