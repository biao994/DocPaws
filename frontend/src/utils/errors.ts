/** 与后端 docpaws/api/response.py ErrorCode 对齐 */
export const ErrorCode = {
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  AUTH_INVALID_CREDENTIALS: 'AUTH_INVALID_CREDENTIALS',
  EMAIL_ALREADY_REGISTERED: 'EMAIL_ALREADY_REGISTERED',
  DOCUMENT_NOT_FOUND: 'DOCUMENT_NOT_FOUND',
  FILE_NOT_FOUND: 'FILE_NOT_FOUND',
  FOLDER_NOT_FOUND: 'FOLDER_NOT_FOUND',
  FOLDER_NOT_EMPTY: 'FOLDER_NOT_EMPTY',
  KB_NOT_FOUND: 'KB_NOT_FOUND',
  KB_EMPTY: 'KB_EMPTY',
  JOB_NOT_FOUND: 'JOB_NOT_FOUND',
  CONVERSATION_NOT_FOUND: 'CONVERSATION_NOT_FOUND',
  FEEDBACK_NOT_FOUND: 'FEEDBACK_NOT_FOUND',
  MESSAGE_NOT_FOUND: 'MESSAGE_NOT_FOUND',
  ANSWER_NOT_FOUND: 'ANSWER_NOT_FOUND',
  INDEX_NOT_READY: 'INDEX_NOT_READY',
  INDEX_FAILED: 'INDEX_FAILED',
  INDEX_FILE_NOT_FOUND: 'INDEX_FILE_NOT_FOUND',
  DUPLICATE_REQUEST: 'DUPLICATE_REQUEST',
  NAME_CONFLICT: 'NAME_CONFLICT',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  RETRIEVAL_FAILED: 'RETRIEVAL_FAILED',
  SEARCH_SERVICE_UNAVAILABLE: 'SEARCH_SERVICE_UNAVAILABLE',
  NO_HIT: 'NO_HIT',
} as const

export type ErrorCodeValue = (typeof ErrorCode)[keyof typeof ErrorCode]

export type ApiErrorPayload = {
  error_code?: string
  message?: string
  user_hint?: string
}

export function getApiErrorPayload(err: unknown): ApiErrorPayload | undefined {
  if (!err || typeof err !== 'object') return undefined
  const response = (err as { response?: { data?: unknown } }).response
  const data = response?.data
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

/** 优先 user_hint，其次 message；与 useChatStream / LoginView 等保持一致 */
export function getApiErrorHint(err: unknown, fallback = '请求失败'): string {
  const payload = getApiErrorPayload(err)
  if (payload?.user_hint) return payload.user_hint
  if (payload?.message) return payload.message
  if (err instanceof Error && err.message) return err.message
  return fallback
}

export function isAbortError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const rec = err as { name?: unknown }
  return rec.name === 'AbortError'
}
