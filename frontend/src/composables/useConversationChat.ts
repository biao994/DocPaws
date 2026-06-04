import { computed, ref, type Ref } from 'vue'

import { deleteConversation, getConversation, listConversationsPaged } from '../api/conversations'
import {
  buildChatScopeBody,
  scopeFromConversation,
  scopeInputPlaceholder,
  type ChatScopePayload,
} from '../api/chatScope'
import { listKnowledgeBases } from '../api/kb'
import type { ChatModalMessage } from '../components/ChatMessageList.vue'
import type { ChatMessage, ConversationItem } from '../types/conversation'
import { isAbortError } from '../utils/errors'
import { setOpenFileChat } from '../utils/openFileChat'
import { useChatMode } from './useChatMode'
import { useChatStream } from './useChatStream'

export type KbOption = {
  id: string
  name: string
  type: string
}

export type ConversationChatMode = 'home' | 'history'

export type UseConversationChatOptions = {
  mode: ConversationChatMode
  pageSize?: number
  /** 加载列表后若无选中会话，自动打开第一条 */
  autoSelectFirst?: boolean
  /** 再次点击当前会话时取消选中（仅 home） */
  toggleDeselect?: boolean
  onScroll?: () => void
  onFileScopeNavigate?: () => void
}

export function useConversationChat(options: UseConversationChatOptions) {
  const {
    mode,
    pageSize = mode === 'home' ? 20 : 50,
    autoSelectFirst = mode === 'history',
    toggleDeselect = mode === 'home',
    onScroll,
    onFileScopeNavigate,
  } = options

  const { chatMode } = useChatMode()
  const { isStreaming, streamingAssistantId, sendChatStream, abort: abortChatStream } = useChatStream()

  const conversations = ref<ConversationItem[]>([])
  const currentConversation = ref<ConversationItem | null>(null)
  const messages = ref<ChatMessage[]>([])
  const activeScope = ref<ChatScopePayload>({ scope_type: 'kb' })
  const errorText = ref('')
  const kbOptions = ref<KbOption[]>([])
  const selectedKb = ref<KbOption | null>(null)
  const draftConversationId = ref<string | null>(null)

  const displayMessages = computed((): ChatModalMessage[] =>
    messages.value.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      thinking: m.thinking,
      citations: m.citations,
    })),
  )

  const chatInputPlaceholder = computed(() => scopeInputPlaceholder(activeScope.value))
  const chatKbId = computed(
    () => currentConversation.value?.kb_id ?? selectedKb.value?.id ?? null,
  )

  const scroll = () => {
    onScroll?.()
  }

  const applyActiveScope = (data: { scope_type?: string; scope_id?: string | null }) => {
    activeScope.value = scopeFromConversation(data)
  }

  const syncSelectedKb = (kbId?: string) => {
    if (!kbId) return
    const match = kbOptions.value.find((k) => k.id === kbId)
    if (match) selectedKb.value = match
  }

  const clearSelectedConversation = () => {
    currentConversation.value = null
    messages.value = []
    activeScope.value = { scope_type: 'kb' }
  }

  const ensureDraftConversation = (): ConversationItem => {
    if (draftConversationId.value) {
      const hit = conversations.value.find((c) => c.id === draftConversationId.value) || null
      if (hit) return hit
    }
    const id = `local-${Date.now()}`
    const draft: ConversationItem = {
      id,
      title: mode === 'history' ? '新对话' : '',
      updated_at: new Date().toISOString(),
      kb_id: selectedKb.value?.id,
    }
    draftConversationId.value = id
    conversations.value = [draft, ...conversations.value]
    return draft
  }

  const redirectFileScopeIfNeeded = (
    item: ConversationItem,
    data: { kb_id?: string } | undefined,
  ): boolean => {
    const scope = activeScope.value
    if (scope.scope_type !== 'file' || !scope.document_id) return false
    const kbId = data?.kb_id || item.kb_id
    if (!kbId) return false
    setOpenFileChat({
      conversationId: item.id,
      documentId: scope.document_id,
      kbId,
    })
    onFileScopeNavigate?.()
    return true
  }

  const selectConversation = async (item: ConversationItem) => {
    if (toggleDeselect && currentConversation.value?.id === item.id) {
      clearSelectedConversation()
      return
    }

    currentConversation.value = item
    applyActiveScope(item)
    syncSelectedKb(item.kb_id)

    if (item.id.startsWith('local-')) {
      activeScope.value = { scope_type: 'kb' }
      messages.value = []
      return
    }

    try {
      const res = await getConversation(item.id)
      const data = res.data?.data
      if (data) {
        applyActiveScope(data)
        syncSelectedKb(data.kb_id)
        if (data.kb_id && currentConversation.value) {
          currentConversation.value = { ...currentConversation.value, kb_id: data.kb_id }
        }
      }
      if (redirectFileScopeIfNeeded(item, data)) return
      messages.value = data?.messages || []
      queueMicrotask(scroll)
    } catch (e) {
      console.error('加载会话详情失败:', e)
      messages.value = []
    }
  }

  const handleDeleteConversation = async (item: ConversationItem) => {
    if (item.id.startsWith('local-')) {
      conversations.value = conversations.value.filter((c) => c.id !== item.id)
      if (draftConversationId.value === item.id) draftConversationId.value = null
      if (currentConversation.value?.id === item.id) clearSelectedConversation()
      return
    }

    try {
      await deleteConversation(item.id)
    } catch (e) {
      console.error('删除会话失败:', e)
      errorText.value = '删除失败，请稍后重试'
      return
    }

    conversations.value = conversations.value.filter((c) => c.id !== item.id)
    if (currentConversation.value?.id === item.id) {
      clearSelectedConversation()
    }
  }

  const loadKnowledgeBases = async () => {
    try {
      const items = await listKnowledgeBases()
      kbOptions.value = items.map((kb) => ({
        id: kb.id,
        name: kb.name,
        type: '个人知识库',
      }))
    } catch (e) {
      console.error('加载知识库失败:', e)
    }
  }

  const loadConversations = async () => {
    try {
      const res = await listConversationsPaged({ page: 1, page_size: pageSize })
      const serverItems: ConversationItem[] = res.data?.data?.items || []
      const drafts = conversations.value.filter((c) => c.id.startsWith('local-'))
      conversations.value = [
        ...drafts,
        ...serverItems.filter((s) => !drafts.some((d) => d.id === s.id)),
      ]
      if (autoSelectFirst && !currentConversation.value && conversations.value.length > 0) {
        await selectConversation(conversations.value[0])
      }
    } catch (e) {
      console.error('加载对话失败:', e)
    }
  }

  const resolveConversationForSend = (): ConversationItem | null => {
    if (currentConversation.value) return currentConversation.value
    if (mode === 'home') {
      const draft = ensureDraftConversation()
      currentConversation.value = draft
      return draft
    }
    return null
  }

  const applyHomeMeta = (conv: ConversationItem, conversationId: string, question: string) => {
    if (!draftConversationId.value || conv.id !== draftConversationId.value) return
    const idx = conversations.value.findIndex((c) => c.id === conv.id)
    if (idx < 0) return
    const titleLimit = 24
    const title = question.length > titleLimit ? `${question.slice(0, titleLimit)}…` : question
    const updated: ConversationItem = {
      ...conversations.value[idx],
      id: conversationId,
      title: conversations.value[idx].title || title,
      updated_at: new Date().toISOString(),
      kb_id: selectedKb.value?.id,
    }
    conversations.value.splice(idx, 1, updated)
    currentConversation.value = updated
    draftConversationId.value = null
  }

  const applyHistoryMeta = (conversationId: string, question: string, kbId: string) => {
    if (currentConversation.value && !currentConversation.value.id.startsWith('local-')) return
    const titleLimit = 30
    const title = question.length > titleLimit ? `${question.slice(0, titleLimit)}…` : question
    const conv: ConversationItem = {
      id: conversationId,
      title,
      updated_at: new Date().toISOString(),
      kb_id: kbId,
    }
    conversations.value = [
      conv,
      ...conversations.value.filter(
        (c) => !c.id.startsWith('local-') && c.id !== conversationId,
      ),
    ]
    currentConversation.value = conv
  }

  const sendMessage = async (question: string) => {
    const kbId = chatKbId.value
    const q = question.trim()
    if (!kbId || !q || isStreaming.value) return false

    errorText.value = ''
    const conv = resolveConversationForSend()
    const conversationId = conv?.id.startsWith('local-') ? undefined : conv?.id

    const userTempId = `u-${Date.now()}`
    const aiTempId = `a-${Date.now()}`
    messages.value.push(
      { id: userTempId, role: 'user', content: q, created_at: new Date().toISOString() },
      { id: aiTempId, role: 'assistant', content: '', created_at: new Date().toISOString() },
    )
    queueMicrotask(scroll)

    try {
      const result = await sendChatStream({
        body: {
          kb_id: kbId,
          question: q,
          conversation_id: conversationId,
          ...buildChatScopeBody(activeScope.value),
          chat_mode: chatMode.value,
        },
        assistantMsgId: aiTempId,
        getAssistantMsg: () => messages.value.find((m) => m.id === aiTempId),
        inlineError: mode === 'history' ? false : true,
        onUnauthorized: () => {
          messages.value = messages.value.filter((m) => m.id !== userTempId && m.id !== aiTempId)
        },
        onMeta: (payload) => {
          if (!payload.conversation_id) return
          if (mode === 'home' && conv) {
            applyHomeMeta(conv, payload.conversation_id, q)
            return
          }
          applyHistoryMeta(payload.conversation_id, q, kbId)
        },
        onChunk: scroll,
        onFinished: (payload) => {
          if (
            mode === 'history' &&
            payload.conversation_id &&
            currentConversation.value?.id.startsWith('local-')
          ) {
            currentConversation.value = {
              ...currentConversation.value,
              id: payload.conversation_id,
            }
          }
        },
      })

      if (result === 'unauthorized') return false

      if (mode === 'history' && currentConversation.value && !currentConversation.value.id.startsWith('local-')) {
        void loadConversations()
      }
      return true
    } catch (e) {
      if (isAbortError(e)) return false
      console.error('发送失败:', e)
      const msg = e instanceof Error ? e.message : '发送失败，请稍后重试'
      const aiMsg = messages.value.find((m) => m.id === aiTempId)
      if (aiMsg) aiMsg.content = `提示：${msg}`
      return false
    }
  }

  const newChat = () => {
    errorText.value = ''
    if (mode === 'history') {
      const draft: ConversationItem = {
        id: `local-${Date.now()}`,
        title: '新对话',
        updated_at: new Date().toISOString(),
        kb_id: selectedKb.value?.id || '',
      }
      conversations.value = [draft, ...conversations.value]
      currentConversation.value = null
      messages.value = []
      activeScope.value = { scope_type: 'kb' }
      return
    }
    draftConversationId.value = null
    clearSelectedConversation()
  }

  const filterConversations = (searchText: Ref<string> | string) => {
    const keyword = (typeof searchText === 'string' ? searchText : searchText.value).trim().toLowerCase()
    if (!keyword) return conversations.value
    return conversations.value.filter((c) => (c.title || '').toLowerCase().includes(keyword))
  }

  const openConversationById = async (id: string | null | undefined) => {
    if (!id) return
    const hit = conversations.value.find((c) => c.id === id) || null
    if (hit) await selectConversation(hit)
  }

  return {
    conversations,
    currentConversation,
    messages,
    activeScope,
    errorText,
    kbOptions,
    selectedKb,
    isStreaming,
    streamingAssistantId,
    displayMessages,
    chatInputPlaceholder,
    chatKbId,
    loadKnowledgeBases,
    loadConversations,
    selectConversation,
    handleDeleteConversation,
    clearSelectedConversation,
    sendMessage,
    newChat,
    filterConversations,
    openConversationById,
    abortChatStream,
  }
}
