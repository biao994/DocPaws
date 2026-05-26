import { http } from './http'

export type ConversationSummary = {
  id: string
  title: string
  updated_at: string
  kb_id?: string
  scope_type?: 'kb' | 'folder' | 'file'
  scope_id?: string | null
}

export async function listConversationsPaged(params?: { page?: number; page_size?: number }) {
  return await http.get('/api/v1/conversations', { params })
}

export async function listKbConversations(
  kbId: string,
  params?: {
    page?: number
    page_size?: number
    scope_type?: 'kb' | 'folder' | 'file'
    scope_id?: string
  },
) {
  return await http.get(`/api/v1/knowledge-bases/${kbId}/conversations`, { params })
}

export async function getConversation(conversationId: string) {
  return await http.get(`/api/v1/conversations/${conversationId}`)
}

export async function renameConversation(conversationId: string, title: string) {
  return await http.patch(`/api/v1/conversations/${conversationId}`, { title })
}

export async function deleteConversation(conversationId: string) {
  return await http.delete(`/api/v1/conversations/${conversationId}`)
}
