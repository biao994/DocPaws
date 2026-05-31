export type PendingAssistantMessage = {
  id: string
  role: string
  content?: string
  thinking?: string
}

/** 流式进行中且尚无正文/思考内容时，展示「正在思考中…」占位。 */
export function isAssistantAwaitingContent(
  msg: PendingAssistantMessage,
  pendingAssistantId: string | null | undefined,
): boolean {
  if (!pendingAssistantId || msg.role !== 'assistant' || msg.id !== pendingAssistantId) {
    return false
  }
  return !String(msg.content ?? '').trim() && !String(msg.thinking ?? '').trim()
}
