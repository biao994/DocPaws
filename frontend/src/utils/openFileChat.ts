/** 从历史/首页跳转到知识库「文件预览 + 侧边对话」时使用的 session 载荷 */

export type OpenFileChatPayload = {
  conversationId: string
  documentId: string
  kbId: string
}

const STORAGE_KEY = 'openFileChat'

export function setOpenFileChat(payload: OpenFileChatPayload) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

export function consumeOpenFileChat(): OpenFileChatPayload | null {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  sessionStorage.removeItem(STORAGE_KEY)
  try {
    const data = JSON.parse(raw) as OpenFileChatPayload
    if (data.conversationId && data.documentId && data.kbId) return data
  } catch {
    /* ignore */
  }
  return null
}
