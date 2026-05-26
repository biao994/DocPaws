export function isAbortError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const rec = err as { name?: unknown }
  return rec.name === 'AbortError'
}

