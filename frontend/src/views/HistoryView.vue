<template>
  <AppShell @toggle-sidebar="toggleSidebar">
    <template #nav-left>
      <button class="top-collapse-btn" type="button" @click="toggleSidebar" title="收起侧边栏">
        <IconChevronLeft />
      </button>
      <button class="top-back-btn" type="button" @click="navigate('home')" title="返回">
        <MascotLogo :size="28" />
      </button>
    </template>

    <div class="main-container">
      <!-- 左侧：导航 + 问答历史（默认展开，符合图一） -->
      <div class="sidebar-left" :class="{ collapsed: sidebarCollapsed }">
        <button class="new-chat-btn" @click="newChat" title="新建会话">
          <span class="new-chat-icon" aria-hidden="true">
            <IconNewChat />
          </span>
          <span class="new-chat-text">新建会话</span>
        </button>

        <button class="nav-item" @click="navigate('kb')">
          <IconFolder />
          <span>知识库</span>
        </button>
        <button class="nav-item active">
          <IconClock />
          <span>历史</span>
        </button>

        <div class="sidebar-section">
          <div class="sidebar-section-header">
            <span class="sidebar-section-title">对话历史</span>
            <button class="btn-icon" title="刷新" @click="loadConversations">↻</button>
          </div>
          <div class="search-box">
            <input class="search-input" placeholder="搜索历史会话..." v-model="searchText" />
          </div>
          <div class="history-list">
            <div
              v-for="item in filteredConversations"
              :key="item.id"
              class="history-item"
              :class="{ active: item.id === currentConversation?.id }"
              @click="selectConversation(item)"
            >
              <div class="history-time-col">{{ formatClock(item.updated_at) }}</div>
              <div class="history-content-col">
                <div class="history-question">{{ item.title || '新对话' }}</div>
                <div class="history-subtext">个人 · {{ formatTime(item.updated_at) }}</div>
              </div>
              <button class="history-delete-btn" title="删除" @click.stop="handleDeleteConversation(item)">
                <IconTrash />
              </button>
            </div>
            <div v-if="filteredConversations.length === 0" class="history-empty">暂无历史会话</div>
          </div>
        </div>
      </div>

      <!-- 右侧聊天区（新增） -->
      <div class="content-area">
        <div class="chat-header">
          <div class="chat-title">
            {{ scopeDisplayLabel(activeScope) }} · {{ currentConversation?.title || '会话详情' }}
          </div>
        </div>
        <div ref="chatContent" class="chat-content">
          <div v-if="!currentConversation" class="chat-empty">
            请选择一条问答历史查看详情
          </div>
          <ChatMessageList
            v-else
            variant="page"
            :messages="displayMessages"
            :pending-assistant-id="streamingAssistantId"
          />
        </div>
        <div class="chat-input">
          <div class="composer-wrap">
            <ComposerBox
              v-model="questionInput"
              shell-variant="card"
              :enable-kb-picker="false"
              :kb-options="kbOptions"
              :selected-kb-id="chatKbId"
              :disabled-send="!chatKbId || !questionInput.trim() || isStreaming"
              :error-text="errorText"
              :show-error-banner="!!errorText"
              :placeholder="chatInputPlaceholder"
              @send="sendQuestion"
              @attachment="openAttachmentDialog"
            />
            <div v-if="selectedAttachmentName" class="attachment-chip">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="display:inline;vertical-align:middle;margin-right:4px">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
              </svg>
              {{ selectedAttachmentName }}
              <button class="attachment-remove" @click="clearAttachment">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import ChatMessageList, { type ChatModalMessage } from '../components/ChatMessageList.vue'
import type { ChatCitation } from '../api/chatTypes'
import ComposerBox from '../components/ComposerBox.vue'
import IconChevronLeft from '../components/icons/IconChevronLeft.vue'
import IconClock from '../components/icons/IconClock.vue'
import IconFolder from '../components/icons/IconFolder.vue'
import IconNewChat from '../components/icons/IconNewChat.vue'
import IconTrash from '../components/icons/IconTrash.vue'
import MascotLogo from '../components/MascotLogo.vue'
import { listKnowledgeBases } from '../api/kb'
import { deleteConversation, getConversation, listConversationsPaged } from '../api/conversations'
import {
  buildChatScopeBody,
  scopeDisplayLabel,
  scopeFromConversation,
  scopeInputPlaceholder,
  type ChatScopePayload,
} from '../api/chatScope'
import { useChatMode } from '../composables/useChatMode'
import { useChatStream } from '../composables/useChatStream'
import { isAbortError } from '../utils/errors'
import { applyKbMentionToInput } from '../utils/kbMention'
import { setOpenFileChat } from '../utils/openFileChat'

type ViewName = 'home' | 'kb' | 'history'
interface KbOption {
  id: string
  name: string
  type: string
}
type Conversation = {
  id: string
  title: string
  updated_at: string
  kb_id: string
  scope_type?: 'kb' | 'folder' | 'file'
  scope_id?: string | null
}
type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  citations?: ChatCitation[]
  created_at: string
}

const { chatMode } = useChatMode()
const { isStreaming, streamingAssistantId, sendChatStream, abort: abortChatStream } = useChatStream()

const emit = defineEmits<{
  (e: 'navigate', view: ViewName): void
}>()

const sidebarCollapsed = ref(false)
const searchText = ref('')
const kbOptions = ref<KbOption[]>([])
const selectedKb = ref<KbOption | null>(null)
const conversations = ref<Conversation[]>([])
const currentConversation = ref<Conversation | null>(null)
const messages = ref<Message[]>([])
const questionInput = ref('')
const errorText = ref('')
const selectedAttachmentName = ref('')
const activeScope = ref<ChatScopePayload>({ scope_type: 'kb' })

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

const applyActiveScope = (data: { scope_type?: string; scope_id?: string | null }) => {
  activeScope.value = scopeFromConversation(data)
}

const newChat = () => {
  errorText.value = ''
  // 历史页不再跳全屏 chat：只插入一条草稿会话到列表最前，并回到空状态
  const draft: Conversation = {
    id: `local-${Date.now()}`,
    title: '新对话',
    updated_at: new Date().toISOString(),
    kb_id: selectedKb.value?.id || '',
  }
  conversations.value = [draft, ...conversations.value]
  currentConversation.value = null
  messages.value = []
  activeScope.value = { scope_type: 'kb' }
}

const openAttachmentDialog = () => {
  // 目前仅占位：不影响输入框样式/主流程
  errorText.value = '附件功能尚未接入'
}

const clearAttachment = () => {
  selectedAttachmentName.value = ''
}

const chatContent = ref<HTMLElement | null>(null)
const settingsMenu = ref<HTMLElement | null>(null)
const userInfo = ref<HTMLElement | null>(null)

const navigate = (view: ViewName) => {
  emit('navigate', view)
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const formatTime = (dateStr: string) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatClock = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

//前端过滤，后面改成后端过滤
const filteredConversations = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  return conversations.value.filter(
    (item) => !keyword || item.title.toLowerCase().includes(keyword)
  )
})

const groupedConversations = computed(() => {
  const toDayKey = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

  const toDayTitle = (key: string) => {
    const [y, m, d] = key.split('-').map((x) => Number(x))
    if (!y || !m || !d) return key
    return `${y}年${m}月${d}日`
  }

  const sorted = [...filteredConversations.value].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  )

  const dayToItems = new Map<string, Conversation[]>()
  for (const item of sorted) {
    const d = new Date(item.updated_at)
    const key = toDayKey(d)
    const list = dayToItems.get(key) || []
    list.push(item)
    dayToItems.set(key, list)
  }

  return [...dayToItems.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : -1)) // key 是 yyyy-mm-dd，可直接字典序倒序
    .map(([key, items]) => ({ title: toDayTitle(key), items }))
})


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

const selectKb = (kb: KbOption) => {
  selectedKb.value = kb
  questionInput.value = applyKbMentionToInput(questionInput.value, kb.name)
}


const loadConversations = async () => {
  try {
    const res = await listConversationsPaged({ page: 1, page_size: 50 })
    const serverItems: Conversation[] = res.data?.data?.items || []
    const drafts = conversations.value.filter((c) => c.id.startsWith('local-'))
    conversations.value = [
      ...drafts,
      ...serverItems.filter((s) => !drafts.some((d) => d.id === s.id)),
    ]
    if (!currentConversation.value && conversations.value.length > 0) {
      await selectConversation(conversations.value[0])
    }
  } catch (e) {
    console.error('加载对话失败:', e)
  }
}

const selectConversation = async (item: Conversation) => {
  currentConversation.value = item
  applyActiveScope(item)
  const match = kbOptions.value.find((k) => k.id === item.kb_id)
  if (match) {
    selectedKb.value = match
  }
  if (item.id.startsWith('local-')) {
    activeScope.value = { scope_type: 'kb' }
    messages.value = []
    return
  }
  const res = await getConversation(item.id)
  const data = res.data?.data
  if (data) {
    applyActiveScope(data)
    if (data.kb_id) {
      const match = kbOptions.value.find((k) => k.id === data.kb_id)
      if (match) selectedKb.value = match
      currentConversation.value = {
        ...item,
        kb_id: data.kb_id,
      }
    }
  }
  const scope = activeScope.value
  if (scope.scope_type === 'file' && scope.document_id) {
    const kbId = data?.kb_id || item.kb_id
    if (kbId) {
      setOpenFileChat({
        conversationId: item.id,
        documentId: scope.document_id,
        kbId,
      })
      emit('navigate', 'kb')
      return
    }
  }
  messages.value = data?.messages || []
}

const handleDeleteConversation = async (item: Conversation) => {
  if (item.id.startsWith('local-')) {
    conversations.value = conversations.value.filter((c) => c.id !== item.id)
    if (currentConversation.value?.id === item.id) {
      currentConversation.value = null
      messages.value = []
      activeScope.value = { scope_type: 'kb' }
    }
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
    currentConversation.value = null
    messages.value = []
    activeScope.value = { scope_type: 'kb' }
  }
}

const scrollToBottom = () => {
  if (chatContent.value) {
    // 滚动到底部
    chatContent.value.scrollTop = chatContent.value.scrollHeight
  }
}

const sendQuestion = async () => {
  const kbIdForChat = chatKbId.value
  if (!kbIdForChat || !questionInput.value.trim() || isStreaming.value) return

  const question = questionInput.value.trim()
  const userTempId = `u-${Date.now()}`
  const aiTempId = `a-${Date.now()}`

  messages.value.push(
    { id: userTempId, role: 'user', content: question, created_at: new Date().toISOString()},
    { id: aiTempId, role: 'assistant', content: '', created_at: new Date().toISOString()}
  )
  questionInput.value = ''
  errorText.value = ''
  scrollToBottom()

  try {
    await sendChatStream({
      body: {
        kb_id: kbIdForChat,
        question,
        conversation_id: currentConversation.value?.id?.startsWith('local-')
          ? undefined
          : currentConversation.value?.id,
        ...buildChatScopeBody(activeScope.value),
        chat_mode: chatMode.value,
      },
      assistantMsgId: aiTempId,
      getAssistantMsg: () => messages.value.find((m) => m.id === aiTempId),
      inlineError: false,
      onUnauthorized: () => {
        messages.value = messages.value.filter((m) => m.id !== userTempId && m.id !== aiTempId)
      },
      onMeta: (payload) => {
        if (!payload.conversation_id) return
        if (!currentConversation.value || currentConversation.value.id.startsWith('local-')) {
          const title = question.length > 30 ? `${question.slice(0, 30)}…` : question
          const conv: Conversation = {
            id: payload.conversation_id,
            title,
            updated_at: new Date().toISOString(),
            kb_id: kbIdForChat,
          }
          conversations.value = [
            conv,
            ...conversations.value.filter(
              (c) => !c.id.startsWith('local-') && c.id !== payload.conversation_id,
            ),
          ]
          currentConversation.value = conv
        }
      },
      onChunk: () => scrollToBottom(),
      onFinished: (payload) => {
        if (payload.conversation_id && currentConversation.value?.id.startsWith('local-')) {
          currentConversation.value = {
            ...currentConversation.value,
            id: payload.conversation_id,
          }
        }
      },
    })
  } catch (e) {
    if (isAbortError(e)) return
    console.error('发送失败:', e)
    const msg = e instanceof Error ? e.message : '发送失败，请稍后重试'
    const aiMsg = messages.value.find((m) => m.id === aiTempId)
    if (aiMsg) aiMsg.content = `提示：${msg}`
  } finally {
    if (currentConversation.value && !currentConversation.value.id.startsWith('local-')) {
      void loadConversations()
    }
  }
}
onMounted(() => {
  void (async () => {
    await loadKnowledgeBases()
    await loadConversations()

    const openId = sessionStorage.getItem('openConversationId')
    if (openId) {
      sessionStorage.removeItem('openConversationId')
      const hit = conversations.value.find((c) => c.id === openId) || null
      if (hit) {
        await selectConversation(hit)
      }
    }
  })()
})

onUnmounted(() => {
  abortChatStream()
})


</script>

<style scoped>
.top-collapse-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  padding: 0;
}

.top-collapse-btn:hover {
  background: #f5f5f5;
}

.top-back-btn {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  padding: 0;
}

.top-back-btn:hover {
  background: #f5f5f5;
}

.main-container {
  display: flex;
  flex: 1;
  min-height: 0;
  position: relative;
  background: #f5f5f5;
}

.sidebar-left {
  width: 280px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  padding: 12px 10px;
  gap: 8px;
}

.sidebar-left.collapsed {
  width: 0;
  overflow: hidden;
  padding: 0;
  border-right: none;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.new-chat-btn {
  width: 100%;
  height: 44px;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.new-chat-btn:hover {
  background: #f7f7f7;
}

.new-chat-text {
  font-size: 13px;
  white-space: nowrap;
}

.nav-item {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  cursor: pointer;
  color: #6b7280;
  font-size: 13px;
  background: transparent;
  border: none;
  padding: 0 10px;
}

.nav-item:hover {
  background: #f5f5f5;
}

.nav-item.active {
  color: var(--dp-primary);
  background: var(--dp-primary-bg);
}

.nav-item svg {
  width: 18px;
  height: 18px;
}

.sidebar-section {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-top: 1px solid #f0f0f0;
  padding-top: 10px;
}

.sidebar-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 6px 8px;
}

.sidebar-section-title {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
}

.btn-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #6b7280;
  font-size: 14px;
}

.btn-icon:hover {
  background: #f5f5f5;
}

.search-box {
  padding: 0 6px 10px;
}

.search-input {
  width: 100%;
  height: 36px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 0 12px;
  font-size: 13px;
  outline: none;
}

.search-input:focus {
  border-color: var(--dp-primary);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px 8px;
}

.history-empty {
  padding: 14px 6px;
  font-size: 12px;
  color: #94a3b8;
}

.history-group {
  margin-bottom: 16px;
}

.group-title {
  font-size: 12px;
  color: #94a3b8;
  padding: 8px 12px;
}

.history-item {
  display: flex;
  align-items: flex-start;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  gap: 12px;
}

.history-item:hover {
  background: #f5f5f5;
}

.history-item.active {
  background: var(--dp-primary-bg);
}

.history-time-col {
  font-size: 12px;
  color: #94a3b8;
  min-width: 40px;
}

.history-content-col {
  flex: 1;
  min-width: 0;
}

.history-delete-btn {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  flex: 0 0 auto;
}

.history-item:hover .history-delete-btn {
  opacity: 1;
}

.history-delete-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #f56c6c;
}

.history-question {
  font-size: 14px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-subtext {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.history-more-wrap {
  position: relative;
}

.history-more-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
  font-size: 14px;
  border-radius: 4px;
}

.history-more-btn:hover {
  background: #f0f0f0;
}

.history-more-menu {
  position: absolute;
  right: 0;
  top: 100%;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  padding: 4px;
  min-width: 80px;
  z-index: 10;
}

.history-more-item {
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
  border-radius: 4px;
}

.history-more-item:hover {
  background: #f5f5f5;
}

.history-more-item.danger {
  color: #f56c6c;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.chat-header {
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}

.chat-title {
  font-size: 14px;
  color: #6b7280;
}

.chat-actions {
  display: flex;
  gap: 12px;
}

.btn-text {
  border: none;
  background: transparent;
  color: var(--dp-primary);
  cursor: pointer;
  font-size: 13px;
}

.btn-text:hover {
  color: var(--dp-primary-hover);
}

.chat-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fff;
}

.chat-empty {
  padding: 18px 12px;
  font-size: 13px;
  color: #94a3b8;
}

.message {
  margin-bottom: 16px;
  display: flex;
}

.message.user {
  justify-content: flex-end;
}

.message.ai {
  justify-content: flex-start;
}

.message-body {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
}

.message.user .message-body {
  background: var(--dp-primary);
  color: #fff;
}

.message.ai .message-body {
  background: #fff;
  color: #6b7280;
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message-meta {
  font-size: 12px;
  margin-top: 8px;
  opacity: 0.7;
}

.source-list {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.source-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.source-item {
  display: flex;
  gap: 8px;
  padding: 8px;
  background: #f9f9f9;
  border-radius: 6px;
  margin-bottom: 8px;
}

.source-icon {
  font-size: 16px;
}

.chat-input {
  padding: 16px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
}

.composer-wrap{
  position: relative;
  width: min(720px, 92%);
}

.dialog-input-shell {
  width: 100%;
  max-width: none;
  background: #fff;
  border-radius: 18px;
  padding: 12px 14px 10px;
  border: 1px solid #e6e6e6;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dialog-input-main-row {
  display: flex;
  align-items: stretch;
}

.scope-pill {
  align-self: flex-start;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--dp-primary-bg);
  color: var(--dp-primary);
  font-size: 12px;
  cursor: pointer;
}

.dialog-input-main{
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  outline: none;
  color: #6b7280;

  resize: none;
  line-height: 22px;
  padding: 2px 6px;
  min-height: 22px;
  max-height: 120px;
  overflow-y: auto;

  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.dialog-input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
}

.dialog-error-banner{
  margin: 2px 6px 0;
  padding: 8px 10px;
  border-radius: 10px;
  background: #fff1f0;
  border: 1px solid #ffccc7;
  color: #a8071a;
  font-size: 12px;
  line-height: 18px;
}

.dialog-left {
  display: flex;
  gap: 8px;
}

.dialog-pill {
  padding: 4px 10px;
  border-radius: 999px;
  border: none;
  background: #f7f7f7;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
}

.dialog-pill:hover{
  background: #efefef;
}

.attachment-chip {
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
}

.attachment-remove {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
}

.dialog-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dialog-icon-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.dialog-send-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: var(--dp-primary);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-send-btn:hover {
  background: var(--dp-primary-hover);
}

.dialog-send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.kb-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 8px;
  min-width: 220px;
  z-index: 110;
}

.kb-dropdown-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.kb-dropdown-item:hover {
  background: #f5f5f5;
}

.kb-dropdown-item.active {
  background: var(--dp-primary-bg);
}

.kb-item-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 2px;
}

.kb-item-name {
  font-size: 14px;
  color: #6b7280;
}
</style>