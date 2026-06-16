import { computed, onScopeDispose, ref } from 'vue'
import { streamChatResponse } from './useChatStream'
import { useChatMode } from './useChatMode'
import { postChat } from '../api/documents'
import {
  deleteConversation,
  getConversation,
  listKbConversations,
  renameConversation,
  type ConversationSummary as ApiConversationSummary,
} from '../api/conversations'
import {
  buildChatScopeBody,
  chatScopeCacheKey,
  listConversationsQueryParams,
  scopeFromConversation,
  type ChatScopePayload,
} from '../api/chatScope'
import { getApiErrorHint, isAbortError } from '../utils/errors'

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
  /** 防止异步加载历史覆盖用户正在进行的对话 */
  let conversationLoadToken = 0

  const assignConversationId = (
    conversationId: string,
    scope: ChatScopePayload,
  ) => {
    modalConversationId.value = conversationId
    if (!lockedScope.value) {
      lockedScope.value = scope
    }
  }

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

  const buildModalScopeKey = (kbId: string) => {
    const scope = lockedScope.value ?? currentScope()
    return `${kbId}|${chatScopeCacheKey(scope)}`
  }

  const markKbSessionsStale = () => {
    conversationLoadToken += 1
    modalLoadedScopeKey.value = null
    modalConversationId.value = null
    modalMessages.value = []
    lockedScope.value = null
  }

  /** 续聊用会话锁定范围；新会话用当前浏览位置 */
  const effectiveScope = computed((): ChatScopePayload => {
    if (lockedScope.value) return lockedScope.value
    return opts.getChatScope?.() ?? { scope_type: 'kb' }
  })

  const loadModalConversations = async (kbId: string) => {
    const scopeParams = listConversationsQueryParams(effectiveScope.value)
    const res = await listKbConversations(kbId, {
      page: 1,
      page_size: 50,
      ...scopeParams,
    })
    const items = (res.data?.data?.items || []) as KbConversationSummary[]
    modalConversations.value = items
    return items
  }

  const applyConversationScope = (
    data: {
      scope_type?: string
      scope_id?: string | null
    },
    options?: { syncBrowseUi?: boolean },
  ) => {
    const scope = scopeFromConversation(data)
    lockedScope.value = scope
    if (options?.syncBrowseUi !== false) {
      opts.onScopeRestored?.(scope)
    }
  }

  const loadModalConversationMessages = async (
    conversationId: string,
    options?: { syncBrowseUi?: boolean },
  ) => {
    const loadToken = conversationLoadToken
    const res = await getConversation(conversationId)
    if (loadToken !== conversationLoadToken) return
    const data = res.data?.data
    if (data) applyConversationScope(data, options)
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
    const loadToken = conversationLoadToken
    try {
      const items = await loadModalConversations(kb.id)
      if (loadToken !== conversationLoadToken) return
      // 用户已在当前范围发起新提问时，不要用「最近会话」覆盖进行中的对话
      if (modalIsStreaming.value || modalMessages.value.length > 0) {
        modalLoadedScopeKey.value = key
        // 本地已有消息但尚未绑定会话 id 时，尽量挂上最近一条以便续聊
        if (!modalConversationId.value) {
          if (items[0]?.id) {
            assignConversationId(items[0].id, resolveRequestScope())
          }
        }
        return
      }
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
      if (loadToken !== conversationLoadToken) return
      modalLoadedScopeKey.value = key
      if (!modalIsStreaming.value && modalMessages.value.length === 0) {
        modalConversationId.value = null
        modalMessages.value = []
        lockedScope.value = null
      }
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
    if (
      modalLoadedScopeKey.value !== key ||
      (!modalConversationId.value && modalMessages.value.length === 0)
    ) {
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
    if (modalIsStreaming.value) return

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
    const conversationIdForRequest = modalConversationId.value ?? undefined
    try {
      disposeStream()
      modalStreamCtrl = new AbortController()
      let streamOk = false
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          const streamResult = await streamChatResponse({
            body: {
              kb_id: kb.id,
              question: rawQuestion,
              conversation_id: modalConversationId.value || conversationIdForRequest,
              ...scopeBody,
              chat_mode: chatMode.value,
            },
            signal: modalStreamCtrl.signal,
            assistantMsgId: aiId,
            inlineError: false,
            getAssistantMsg: () => modalMessages.value.find((m) => m.id === aiId),
            onMeta: (data) => {
              if (data.conversation_id) {
                assignConversationId(data.conversation_id, scope)
              }
            },
            onFinished: (data) => {
              streamOk = true
              if (data.conversation_id) {
                assignConversationId(data.conversation_id, scope)
              }
            },
          })
          if (streamResult === 'unauthorized') {
            const msg = modalMessages.value.find((m) => m.id === aiId)
            if (msg) msg.content = '登录已失效，请重新登录'
            modalIsStreaming.value = false
            return
          }
          if (streamOk) break
        } catch (streamErr) {
          if (isAbortError(streamErr)) throw streamErr
          // 业务错误（含 user_hint）不重试，交给外层统一展示
          if (getApiErrorHint(streamErr, '')) throw streamErr
          /* retry on transient network errors */
        }
        if (attempt === 1) break
        await new Promise((resolve) => setTimeout(resolve, 500))
      }

      if (!streamOk) {
        const res = await postChat({
          kb_id: kb.id,
          question: rawQuestion,
          conversation_id: modalConversationId.value || conversationIdForRequest,
          ...scopeBody,
          chat_mode: chatMode.value,
        })
        const msg = modalMessages.value.find((m) => m.id === aiId)
        if (msg) {
          msg.content = res.data?.data?.answer || '暂无回答'
          msg.citations = (res.data?.data?.citations as KbModalCitation[] | undefined) ?? []
        }
        if (res.data?.data?.conversation_id) {
          assignConversationId(res.data.data.conversation_id, scope)
        }
      } else if (!modalConversationId.value) {
        const items = await loadModalConversations(kb.id)
        if (items[0]?.id) {
          assignConversationId(items[0].id, scope)
        }
      }
      await loadModalConversations(kb.id)
      if (modalConversationId.value) {
        await loadModalConversationMessages(modalConversationId.value, { syncBrowseUi: false })
      }
    } catch (error) {
      if (isAbortError(error)) return
      console.error('Ask in modal failed:', error)
      const msg = modalMessages.value.find((m) => m.id === aiId)
      if (msg) {
        msg.content = `提示：${getApiErrorHint(error, '请求失败，请稍后重试')}`
      }
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
