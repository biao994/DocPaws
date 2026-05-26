export type ChatStreamPayload = {
  event?: string
  content?: string
  finished?: boolean
  conversation_id?: string
  code?: string
  citations?: unknown
}

type StreamCallbacks = {
  onPayload: (p: ChatStreamPayload) => void | Promise<void>
}

function extractDataLine(block: string): string | null {
  // 兼容 "data:" / "data: " 两种写法
  const line =
    block
      .split('\n')
      .find((l) => l.startsWith('data:')) ?? null
  if (!line) return null
  return line.slice('data:'.length).trim()
}

/**
 * 读取后端 SSE（以 "\n\n" 分隔）的 chat stream。
 * - 自动处理分块、缓存残留 buffer
 * - 自动容错 JSON.parse（坏包直接跳过）
 * - 不在这里做业务判断（meta/error/finished 的语义由调用方决定）
 */
export async function readChatSse(
  res: Response,
  cb: StreamCallbacks,
): Promise<void> {
  if (!res.body) throw new Error('响应体为空')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const jsonStr = extractDataLine(part)
      if (!jsonStr) continue
      let payload: ChatStreamPayload | null = null
      try {
        payload = JSON.parse(jsonStr) as ChatStreamPayload
      } catch {
        continue
      }
      await cb.onPayload(payload)
    }
  }
}

