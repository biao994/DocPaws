export type ConversationItem = {
  id: string
  title: string
  updated_at: string
  kb_id?: string
  scope_type?: 'kb' | 'folder' | 'file'
  scope_id?: string | null
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  citations?: import('../api/chatTypes').ChatCitation[]
  created_at: string
}
