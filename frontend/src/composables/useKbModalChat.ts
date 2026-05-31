import { computed, onScopeDispose, ref } from 'vue'
import { readChatSse, type ChatStreamPayload } from '../api/chatStream'
import { applyChatStreamToAssistant } from '../api/chatStreamHandlers'
import { useChatMode } from './useChatMode'
import { postChat } from '../api/documents'
import {
  deleteConversation,
  getConversation,
  listKbConversations,
  renameConversation,
  type ConversationSummary as ApiConversationSummary,
} from '../api/conversations'
import { CHAT_STREAM_URL } from '../api/chat'
import {
  buildChatScopeBody,
  chatScopeCacheKey,
  listConversationsQueryParams,
  scopeFromConversation,
  type ChatScopePayload,
} from '../api/chatScope'
import { applyFetchUnauthorized } from '../auth/session'
import { isAbortError } from '../utils/errors'

export type KbModalChatTarget = { id: string }

export type KbModalCitation = {
  chunk_id: string
  document_id?: string
  page_no?: number
  snippet: string
  source?: string
}

export type KbModalMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  citations?: KbModalCitation[]
}

export type KbConversationSummary = Pick<ApiConversationSummary, 'id' | 'title' | 'updated_at'>

function formatHistoryDate(dateStr: string) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

export function useKbModalChat(opts: {
  ensureSelectedKb: () => Promise<KbModalChatTarget | null>
  getChatScope?: () => ChatScopePayload
  onScopeRestored?: (scope: ChatScopePayload) => void
}) {
  const { chatMode } = useChatMode()
  const showChatModal = ref(false)
  const modalMessages = ref<KbModalMessage[]>([])
  const modalInput = ref('')
  const modalIsStreaming = ref(false)
  const modalStreamingAssistantId = ref<string | null>(null)
  let modalStreamCtrl: AbortController | null = null
  const modalConversationId = ref<string | null>(null)
  const modalConversations = ref<KbConversationSummary[]>([])
  const showModalHistoryPanel = ref(false)
  const modalExpanded = ref(false)
  /** kbId + 对话范围；切换 KB 或 folder/file 时置空以触发重新加载 */
  const modalLoadedScopeKey = ref<string | null>(null)
  const openConversationMenuId = ref<string | null>(null)
  /** 续聊时会话锁定范围；新会话用 getChatScope() */
  const lockedScope = ref<ChatScopePayload | null>(null)

  const disposeStream = () => {
    if (modalStreamCtrl) {
      modalStreamCtrl.abort()
      modalStreamCtrl = null
    }
  }

  onScopeDispose(disposeStream)

  const modalConversationGroups = computed(() => {
    const sorted = [...modalConversations.value].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    )
    const groups = new Map<string, KbConversationSummary[]>()
    for (const c of sorted) {
      const label = formatHistoryDate(c.updated_at)
      if (!groups.has(label)) groups.set(label, [])
      groups.get(label)!.push(c)
    }
    return Array.from(groups.entries()).map(([label, items]) => ({ label, items }))
  })

  const currentScope = (): ChatScopePayload => opts.getChatScope?.() ?? { scope_type: 'kb' }

  const buildModalScopeKey = (kbId: string) =>
    `${kbId}|${chatScopeCacheKey(currentScope())}`

  const markKbSessionsStale = () => {
    modalLoadedScopeKey.value = null
    modalConversationId.value = null
    modalMessages.value = []
    lockedScope.value = null
  }

  const loadModalConversations = async (kbId: string) => {
    const scopeParams = listConversationsQueryParams(currentScope())
    const res = await listKbConversations(kbId, {
      page: 1,
      page_size: 50,
      ...scopeParams,
    })
    const items = (res.data?.data?.items || []) as KbConversationSummary[]
    modalConversations.value = items
    return items
  }

  const applyConversationScope = (data: {
    scope_type?: string
    scope_id?: string | null
  }) => {
    const scope = scopeFromConversation(data)
    lockedScope.value = scope
    opts.onScopeRestored?.(scope)
  }

  /** 续聊用会话锁定范围；新会话用当前浏览位置 */
  const effectiveScope = computed((): ChatScopePayload => {
    if (lockedScope.value) return lockedScope.value
    return opts.getChatScope?.() ?? { scope_type: 'kb' }
  })

  const loadModalConversationMessages = async (conversationId: string) => {
    const res = await getConversation(conversationId)
    const data = res.data?.data
    if (data) applyConversationScope(data)
    const items = data?.messages || []
    modalMessages.value = items.map(
      (m: {
        id: string
        role: 'user' | 'assistant'
        content: string
        citations?: KbModalCitation[]
      }) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        citations: m.citations?.length ? m.citations : [],
      }),
    )
  }

  const resolveRequestScope = (): ChatScopePayload => {
    if (lockedScope.value) return lockedScope.value
    return opts.getChatScope?.() ?? { scope_type: 'kb' }
  }

  const loadLatestConversationForReader = async () => {
    const kb = await opts.ensureSelectedKb()
    if (!kb) return
    const key = buildModalScopeKey(kb.id)
    try {
      const items = await loadModalConversations(kb.id)
      modalLoadedScopeKey.value = key
      if (items[0]?.id) {
        modalConversationId.value = items[0].id
        await loadModalConversationMessages(items[0].id)
      } else {
        modalConversationId.value = null
        modalMessages.value = []
        lockedScope.value = null
      }
    } catch {
      modalLoadedScopeKey.value = key
      modalConversationId.value = null
      modalMessages.value = []
      lockedScope.value = null
    }
  }

  const openModalConversation = async (conversationId: string) => {
    modalConversationId.value = conversationId
    await loadModalConversationMessages(conversationId)
  }

  /** PDF 阅读器侧边栏：打开指定会话并锁定范围 */
  const openReaderWithConversation = async (conversationId: string) => {
    await openModalConversation(conversationId)
    const kb = await opts.ensureSelectedKb()
    if (kb) modalLoadedScopeKey.value = buildModalScopeKey(kb.id)
  }

  const openChatModalFromInput = async () => {
    showChatModal.value = true
    const kb = await opts.ensureSelectedKb()
    if (!kb) return
    const key = buildModalScopeKey(kb.id)
    if (modalLoadedScopeKey.value !== key) {
      await loadLatestConversationForReader()
    }
  }

  const newModalConversation = () => {
    modalConversationId.value = null
    modalMessages.value = []
    lockedScope.value = null
    openConversationMenuId.value = null
  }

  const toggleModalHistory = () => {
    showModalHistoryPanel.value = !showModalHistoryPanel.value
  }

  const toggleModalExpand = () => {
    modalExpanded.value = !modalExpanded.value
  }

  const toggleConversationMenu = (conversationId: string) => {
    openConversationMenuId.value =
      openConversationMenuId.value === conversationId ? null : conversationId
  }

  const renameModalConversation = async (c: {
    id: string
    title?: string | null
    updated_at: string
  }) => {
    const nextTitle = prompt('请输入新的会话名称', c.title || '新会话')?.trim()
    openConversationMenuId.value = null
    if (!nextTitle) return
    try {
      await renameConversation(c.id, nextTitle)
      const kb = await opts.ensureSelectedKb()
      if (kb) await loadModalConversations(kb.id)
    } catch (error) {
      console.error('Rename conversation failed:', error)
      alert('重命名失败')
    }
  }

  const deleteModalConversation = async (conversationId: string) => {
    if (!confirm('确定删除该会话吗？')) return
    openConversationMenuId.value = null
    try {
      await deleteConversation(conversationId)
      if (modalConversationId.value === conversationId) {
        modalConversationId.value = null
        modalMessages.value = []
        lockedScope.value = null
      }
      const kb = await opts.ensureSelectedKb()
      if (kb) {
        const items = await loadModalConversations(kb.id)
        if (!modalConversationId.value && items[0]?.id) {
          modalConversationId.value = items[0].id
          await loadModalConversationMessages(items[0].id)
        }
      }
    } catch (error) {
      console.error('Delete conversation failed:', error)
      alert('删除会话失败')
    }
  }

  const askInModal = async (rawQuestion: string) => {
    const kb = await opts.ensureSelectedKb()
    if (!kb) {
      alert('个人知识库初始化失败，请检查后端服务')
      return
    }
    const userId = `m-u-${Date.now()}`
    const aiId = `m-a-${Date.now()}`
    modalMessages.value.push(
      { id: userId, role: 'user', content: rawQuestion },
      { id: aiId, role: 'assistant', content: '' },
    )
    modalIsStreaming.value = true
    modalStreamingAssistantId.value = aiId
    const scope = resolveRequestScope()
    const scopeBody = buildChatScopeBody(scope)
    try {
      disposeStream()
      modalStreamCtrl = new AbortController()
      let streamOk = false
      for (let attempt = 0; attempt < 2; attempt++) {
        const res = await fetch(CHAT_STREAM_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          signal: modalStreamCtrl.signal,
          body: JSON.stringify({
            kb_id: kb.id,
            question: rawQuestion,
            conversation_id: modalConversationId.value || undefined,
            ...scopeBody,
            chat_mode: chatMode.value,
          }),
        })
        if (res.status === 401) {
          applyFetchUnauthorized()
          const msg = modalMessages.value.find((m) => m.id === aiId)
          if (msg) msg.content = '登录已失效，请重新登录'
          modalIsStreaming.value = false
          return
        }
        if (!res.ok || !res.body) {
          if (attempt === 1) break
          await new Promise((resolve) => setTimeout(resolve, 500))
          continue
        }
        await readChatSse(res, {
          onPayload: async (data: ChatStreamPayload) => {
            if (data.content) {
              const msg = modalMessages.value.find((m) => m.id === aiId)
              if (msg) applyChatStreamToAssistant(data, msg)
            }
            if (data.finished) {
              streamOk = true
              if (data.conversation_id && !modalConversationId.value) {
                modalConversationId.value = data.conversation_id
                if (!lockedScope.value) {
                  lockedScope.value = scope
                }
              }
              const msg = modalMessages.value.find((m) => m.id === aiId)
              if (msg) msg.citations = (data.citations as KbModalCitation[]) || []
            }
          },
        })
        if (streamOk) break
      }

      if (!streamOk) {
        const res = await postChat({
          kb_id: kb.id,
          question: rawQuestion,
          conversation_id: modalConversationId.value || undefined,
          ...scopeBody,
          chat_mode: chatMode.value,
        })
        const msg = modalMessages.value.find((m) => m.id === aiId)
        if (msg) {
          msg.content = res.data?.data?.answer || '暂无回答'
          msg.citations = (res.data?.data?.citations as KbModalCitation[] | undefined) ?? []
        }
        if (res.data?.data?.conversation_id) {
          modalConversationId.value = res.data.data.conversation_id
          if (!lockedScope.value) lockedScope.value = scope
        }
      } else if (!modalConversationId.value) {
        const items = await loadModalConversations(kb.id)
        if (items[0]?.id) {
          modalConversationId.value = items[0].id
        }
      }
      await loadModalConversations(kb.id)
    } catch (error) {
      if (isAbortError(error)) return
      console.error('Ask in modal failed:', error)
      const msg = modalMessages.value.find((m) => m.id === aiId)
      if (msg) msg.content = '请求失败，请重试'
    } finally {
      modalIsStreaming.value = false
      modalStreamingAssistantId.value = null
      modalStreamCtrl = null
    }
  }

  const sendModalQuestion = async () => {
    const q = modalInput.value.trim()
    if (!q || modalIsStreaming.value) return
    modalInput.value = ''
    await askInModal(q)
  }

  const closeChatModal = () => {
    showChatModal.value = false
    showModalHistoryPanel.value = false
    modalExpanded.value = false
    openConversationMenuId.value = null
    disposeStream()
  }

  return {
    showChatModal,
    modalMessages,
    modalInput,
    modalIsStreaming,
    modalStreamingAssistantId,
    modalConversationId,
    modalConversations,
    showModalHistoryPanel,
    modalExpanded,
    modalLoadedScopeKey,
    openConversationMenuId,
    effectiveScope,
    modalConversationGroups,
    markKbSessionsStale,
    loadLatestConversationForReader,
    openModalConversation,
    openReaderWithConversation,
    openChatModalFromInput,
    newModalConversation,
    toggleModalHistory,
    toggleModalExpand,
    toggleConversationMenu,
    renameModalConversation,
    deleteModalConversation,
    askInModal,
    sendModalQuestion,
    closeChatModal,
  }
}
