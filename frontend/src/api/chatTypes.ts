export type ChatCitation = {
  chunk_id: string
  document_id?: string
  page_no?: number
  snippet: string
  source?: string
}

export type StreamableMessage = {
  content: string
  thinking?: string
  citations?: ChatCitation[]
}
