import { ref } from 'vue'

import { CHAT_STREAM_URL } from '../api/chat'
import { readChatSse, type ChatStreamPayload } from '../api/chatStream'
import { applyChatStreamToAssistant } from '../api/chatStreamHandlers'
import type { ChatCitation, StreamableMessage } from '../api/chatTypes'
import { applyFetchUnauthorized } from '../auth/session'
import { isAbortError } from '../utils/errors'

export type { StreamableMessage } from '../api/chatTypes'

export type StreamChatResult = 'ok' | 'unauthorized' | 'failed'

export type StreamChatOptions = {
  body: Record<string, unknown>
  signal?: AbortSignal
  assistantMsgId: string
  getAssistantMsg: () => StreamableMessage | undefined
  onUnauthorized?: () => void
  onMeta?: (payload: ChatStreamPayload) => void
  onError?: (message: string, payload: ChatStreamPayload) => void | 'handled'
  onChunk?: () => void
  onFinished?: (payload: ChatStreamPayload) => void
  /** false 时在 HTTP/SSE 错误处 throw，由调用方 catch */
  inlineError?: boolean
}

async function parseHttpError(res: Response): Promise<string> {
  let hint = '请求失败'
  try {
    const data = await res.json()
    hint = data?.user_hint || data?.message || hint
  } catch {
    /* noop */
  }
  return hint
}

/** 低层 SSE 聊天流：供 composable 与 modal retry 复用。 */
export async function streamChatResponse(options: StreamChatOptions): Promise<StreamChatResult> {
  const {
    body,
    signal,
    getAssistantMsg,
    onUnauthorized,
    onMeta,
    onError,
    onChunk,
    onFinished,
    inlineError = true,
  } = options

  const res = await fetch(CHAT_STREAM_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal,
    body: JSON.stringify(body),
  })

  if (res.status === 401) {
    applyFetchUnauthorized()
    onUnauthorized?.()
    return 'unauthorized'
  }

  if (!res.ok || !res.body) {
    const hint = await parseHttpError(res)
    if (inlineError) {
      const aiMsg = getAssistantMsg()
      if (aiMsg) aiMsg.content = `提示：${hint}`
      return 'failed'
    }
    throw new Error(hint)
  }

  let done = false
  await readChatSse(res, {
    onPayload: async (data: ChatStreamPayload) => {
      if (done) return

      if (data.event === 'meta' && data.conversation_id) {
        onMeta?.(data)
        return
      }

      if (data.event === 'error' || data.code) {
        const message = String(data.content || '处理失败')
        if (onError?.(message, data) === 'handled') {
          done = true
          return
        }
        if (inlineError) {
          const aiMsg = getAssistantMsg()
          if (aiMsg) aiMsg.content = `提示：${message}`
          done = true
          return
        }
        throw new Error(message)
      }

      if (data.content) {
        const aiMsg = getAssistantMsg()
        if (aiMsg) {
          applyChatStreamToAssistant(data, aiMsg)
          onChunk?.()
        }
      }

      if (data.finished) {
        const aiMsg = getAssistantMsg()
        if (aiMsg && data.citations) {
          aiMsg.citations = data.citations as ChatCitation[]
        }
        onFinished?.(data)
        done = true
      }
    },
  })

  return 'ok'
}

export function useChatStream() {
  const isStreaming = ref(false)
  const streamingAssistantId = ref<string | null>(null)
  let streamCtrl: AbortController | null = null

  const abort = () => {
    if (streamCtrl) {
      streamCtrl.abort()
      streamCtrl = null
    }
  }

  async function sendChatStream(options: Omit<StreamChatOptions, 'signal'>): Promise<StreamChatResult> {
    abort()
    streamCtrl = new AbortController()
    isStreaming.value = true
    streamingAssistantId.value = options.assistantMsgId

    try {
      return await streamChatResponse({
        ...options,
        signal: streamCtrl.signal,
      })
    } catch (e) {
      if (isAbortError(e)) return 'failed'
      if (options.inlineError !== false) {
        const aiMsg = options.getAssistantMsg()
        if (aiMsg) {
          aiMsg.content = e instanceof Error ? `提示：${e.message}` : '提示：请求失败，请稍后重试'
        }
        return 'failed'
      }
      throw e
    } finally {
      isStreaming.value = false
      streamingAssistantId.value = null
      streamCtrl = null
    }
  }

  return {
    isStreaming,
    streamingAssistantId,
    sendChatStream,
    abort,
  }
}
