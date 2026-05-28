import { describe, expect, it } from 'vitest'
import { parseIndexJobProgress, unwrapIndexJobPayload } from './indexJobs'

describe('parseIndexJobProgress', () => {
  it('parses number and string', () => {
    expect(parseIndexJobProgress(42)).toBe(42)
    expect(parseIndexJobProgress('80')).toBe(80)
    expect(parseIndexJobProgress(undefined)).toBe(0)
  })
})

describe('unwrapIndexJobPayload', () => {
  it('unwraps { data: job }', () => {
    const job = { id: 'j1', status: 'running', progress: 20 }
    expect(unwrapIndexJobPayload({ data: job })).toEqual(job)
  })

  it('accepts flat job object', () => {
    const job = { id: 'j2', status: 'queued', progress: 0 }
    expect(unwrapIndexJobPayload(job)).toEqual(job)
  })
})
