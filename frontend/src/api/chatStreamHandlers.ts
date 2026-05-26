import type { ChatStreamPayload } from './chatStream'

export type StreamableAssistantMessage = {
  content: string
  thinking?: string
}

/** 将 SSE 载荷写入助手消息（区分思考过程与正文）。 */
export function applyChatStreamToAssistant(
  data: ChatStreamPayload,
  msg: StreamableAssistantMessage,
): void {
  const ev = data.event
  const chunk = data.content ?? ''
  if (!chunk) return

  if (ev === 'thinking_chunk') {
    msg.thinking = (msg.thinking ?? '') + String(chunk)
    return
  }

  if (ev === 'answer_chunk' || ev === undefined || ev === '') {
    msg.content += String(chunk)
  }
}
