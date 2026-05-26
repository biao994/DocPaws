/** 对话检索范围（与后端 ChatRequest / Conversation 对齐） */
export type ChatScopeType = 'kb' | 'folder' | 'file'

export type ChatScopePayload = {
  scope_type: ChatScopeType
  document_id?: string
  folder_id?: string
}

export function buildChatScopeBody(scope: ChatScopePayload): {
  document_id?: string
  folder_id?: string
} {
  if (scope.scope_type === 'file' && scope.document_id) {
    return { document_id: scope.document_id }
  }
  if (scope.scope_type === 'folder' && scope.folder_id) {
    return { folder_id: scope.folder_id }
  }
  return {}
}

/** 会话列表缓存键（同一 KB 下按范围隔离） */
export function chatScopeCacheKey(scope: ChatScopePayload): string {
  if (scope.scope_type === 'file' && scope.document_id) return `file:${scope.document_id}`
  if (scope.scope_type === 'folder' && scope.folder_id) return `folder:${scope.folder_id}`
  return 'kb'
}

/** GET /knowledge-bases/{id}/conversations 的 scope 查询参数 */
export function listConversationsQueryParams(scope: ChatScopePayload): {
  scope_type: ChatScopeType
  scope_id?: string
} {
  if (scope.scope_type === 'file' && scope.document_id) {
    return { scope_type: 'file', scope_id: scope.document_id }
  }
  if (scope.scope_type === 'folder' && scope.folder_id) {
    return { scope_type: 'folder', scope_id: scope.folder_id }
  }
  return { scope_type: 'kb' }
}

/** 从会话详情 / 列表项还原对话范围 */
export function scopeFromConversation(data: {
  scope_type?: string
  scope_id?: string | null
}): ChatScopePayload {
  const st = (data.scope_type || 'kb') as ChatScopeType
  const sid = data.scope_id ?? undefined
  if (st === 'file' && sid) return { scope_type: 'file', document_id: sid }
  if (st === 'folder' && sid) return { scope_type: 'folder', folder_id: sid }
  return { scope_type: 'kb' }
}

export function scopeDisplayLabel(scope: ChatScopePayload): string {
  if (scope.scope_type === 'file') return '文件'
  if (scope.scope_type === 'folder') return '文件夹'
  return '知识库'
}

export function scopeInputPlaceholder(scope: ChatScopePayload): string {
  if (scope.scope_type === 'file') return '基于当前文件提问'
  if (scope.scope_type === 'folder') return '基于当前文件夹提问'
  return '基于知识库提问'
}
