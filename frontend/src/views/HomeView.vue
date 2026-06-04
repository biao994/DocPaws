<template>
  <AppShell @toggle-sidebar="toggleSidebar">
    <div class="main-container">
      <!-- 左侧边栏 -->
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

        <div class="sidebar-section">
          <div class="sidebar-section-header">
            <span class="sidebar-section-title">对话历史</span>
            <button class="btn-icon" title="搜索" @click="toggleHistorySearch">
              <IconSearch />
            </button>
          </div>
          <div v-if="showHistorySearch" class="search-box">
            <input
              ref="historySearchInput"
              class="search-input"
              placeholder="搜索对话历史..."
              v-model="historySearchText"
            />
          </div>
          <div class="history-list">
            <div
              v-for="item in filteredConversations"
              :key="item.id"
              class="history-item"
              :class="{ active: item.id === currentConversation?.id }"
              @click="selectConversation(item)"
            >
              <div class="history-question">{{ item.title || '新对话' }}</div>
              <button class="history-delete-btn" title="删除" @click.stop="handleDeleteConversation(item)">
                <IconTrash />
              </button>
            </div>
            <div v-if="filteredConversations.length === 0" class="history-empty">暂无历史会话</div>
          </div>
        </div>
      </div>

      <!-- 右侧内容区：默认首页；选中会话后展示详情（不跳转历史页） -->
      <div class="content-area">
        <template v-if="currentConversation">
          <div class="chat-header">
            <div class="chat-title">{{ scopeDisplayLabel(activeScope) }} · {{ currentConversation.title }}</div>
          </div>
          <div ref="chatContent" class="chat-content">
            <ChatMessageList
              variant="page"
              :messages="displayMessages"
              :pending-assistant-id="streamingAssistantId"
            />
          </div>
          <div class="chat-input">
            <div class="composer-wrap">
              <ComposerBox
                v-model="inputValue"
                shell-variant="card"
                :enable-kb-picker="false"
                :kb-options="kbOptions"
                :selected-kb-id="chatKbId"
                :disabled-send="!chatKbId || !inputValue.trim()"
                :error-text="errorText"
                :show-error-banner="false"
                :placeholder="chatInputPlaceholder"
                @send="sendFromHome"
              />
            </div>
          </div>
        </template>

        <div v-else class="home-content">
          <div class="home-logo">
            <MascotLogo />
          </div>
          <div class="home-title">DocPaws</div>
          <div class="home-subtitle">猫爪轻轻一拍，就给你答案</div>

          <!-- 底部输入栏 -->
          <div class="ai-input-bar">
            <div class="composer-wrap">
              <ComposerBox
                v-model="inputValue"
                shell-variant="card"
                :kb-options="kbOptions"
                :selected-kb-id="selectedKb?.id ?? null"
                :disabled-send="!selectedKb || !inputValue.trim()"
                :error-text="errorText"
                :show-error-banner="false"
                :placeholder="chatInputPlaceholder"
                @send="sendFromHome"
                @select-kb="selectKb"
              />
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
import IconFolder from '../components/icons/IconFolder.vue'
import IconNewChat from '../components/icons/IconNewChat.vue'
import IconSearch from '../components/icons/IconSearch.vue'
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
import { applyKbMentionToInput } from '../utils/kbMention'
import { setOpenFileChat } from '../utils/openFileChat'
// 定义视图类型
type ViewName = 'home' | 'kb' | 'history'

interface KbOption {
  id: string
  name: string
  type: string
}
// 定义组件事件
const emit = defineEmits<{
  (e: 'navigate', view: ViewName): void
}>()

const sidebarCollapsed = ref(false)
const inputValue = ref('')
const errorText = ref('')

type Conversation = {
  id: string
  title: string
  updated_at: string
  kb_id?: string
  scope_type?: 'kb' | 'folder' | 'file'
  scope_id?: string | null
}
const conversations = ref<Conversation[]>([])
const showHistorySearch = ref(false)
const historySearchText = ref('')
const historySearchInput = ref<HTMLInputElement | null>(null)
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
const draftConversationId = ref<string | null>(null)
const currentConversation = ref<Conversation | null>(null)
const messages = ref<Message[]>([])
const chatContent = ref<HTMLElement | null>(null)

const displayMessages = computed((): ChatModalMessage[] =>
  messages.value.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    thinking: m.thinking,
    citations: m.citations,
  })),
)
/** 当前会话的问答范围（续聊时与创建会话时一致） */
const activeScope = ref<ChatScopePayload>({ scope_type: 'kb' })

const chatInputPlaceholder = computed(() => scopeInputPlaceholder(activeScope.value))

/** 续聊历史会话时固定 kb_id，不可通过 @ 切换 */
const chatKbId = computed(
  () => currentConversation.value?.kb_id ?? selectedKb.value?.id ?? null,
)

//知识库相关状态
const kbOptions = ref<KbOption[]>([])
const selectedKb = ref<KbOption | null>(null)

// 导航
const navigate = (view: ViewName) => {
  emit('navigate', view)
}

const filteredConversations = computed(() => {
  const keyword = historySearchText.value.trim().toLowerCase()
  if (!keyword) return conversations.value
  return conversations.value.filter((c) => (c.title || '').toLowerCase().includes(keyword))
})

const toggleHistorySearch = () => {
  showHistorySearch.value = !showHistorySearch.value
  if (showHistorySearch.value) {
    queueMicrotask(() => historySearchInput.value?.focus())
  } else {
    historySearchText.value = ''
  }
}

const scrollToBottom = () => {
  if (chatContent.value) {
    chatContent.value.scrollTop = chatContent.value.scrollHeight
  }
}

const ensureDraftConversation = (): Conversation => {
  if (draftConversationId.value) {
    const hit = conversations.value.find((c) => c.id === draftConversationId.value) || null
    if (hit) return hit
  }
  const id = `local-${Date.now()}`
  const draft: Conversation = {
    id,
    title: '', // 标题在用户输入提问后再生成
    updated_at: new Date().toISOString(),
    kb_id: selectedKb.value?.id,
  }
  draftConversationId.value = id
  conversations.value = [draft, ...conversations.value]
  return draft
}

const applyActiveScope = (data: { scope_type?: string; scope_id?: string | null }) => {
  activeScope.value = scopeFromConversation(data)
}

const syncSelectedKb = (kbId?: string) => {
  if (!kbId) return
  const match = kbOptions.value.find((k) => k.id === kbId)
  if (match) selectedKb.value = match
}

const selectConversation = async (item: Conversation) => {
  if (currentConversation.value?.id === item.id) {
    clearSelectedConversation()
    return
  }
  currentConversation.value = item
  applyActiveScope(item)
  syncSelectedKb(item.kb_id)
  // 本地草稿会话：不请求后端，直接展示空消息
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
    queueMicrotask(scrollToBottom)
  } catch (e) {
    console.error('加载会话详情失败:', e)
    messages.value = []
  }
}

const clearSelectedConversation = () => {
  currentConversation.value = null
  messages.value = []
  activeScope.value = { scope_type: 'kb' }
}

const handleDeleteConversation = async (item: Conversation) => {
  // 本地草稿：直接移除
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

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

// 选择知识库
const selectKb = (kb: KbOption) => {
  selectedKb.value = kb
  inputValue.value = applyKbMentionToInput(inputValue.value, kb.name)
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
    const res = await listConversationsPaged({ page: 1, page_size: 20 })
    const serverItems: Conversation[] = res.data?.data?.items || []
    const drafts = conversations.value.filter((c) => c.id.startsWith('local-'))
    const merged = [
      ...drafts,
      ...serverItems.filter((s) => !drafts.some((d) => d.id === s.id)),
    ]
    conversations.value = merged
  } catch (e) {
    console.error('加载对话失败:', e)
  }
}

const sendFromHome = async () => {
  const q = inputValue.value.trim()
  const kbId = chatKbId.value
  if (!kbId || !q || isStreaming.value) return

  errorText.value = ''

  // 第一次发送：在“对话历史”最前插入草稿，并切到右侧详情
  const conv = currentConversation.value || ensureDraftConversation()
  if (!currentConversation.value) {
    currentConversation.value = conv
  }

  const userTempId = `u-${Date.now()}`
  const aiTempId = `a-${Date.now()}`
  messages.value.push(
    { id: userTempId, role: 'user', content: q, created_at: new Date().toISOString() },
    { id: aiTempId, role: 'assistant', content: '', created_at: new Date().toISOString() },
  )
  inputValue.value = ''
  queueMicrotask(scrollToBottom)

  const result = await sendChatStream({
    body: {
      kb_id: kbId,
      question: q,
      conversation_id: conv.id.startsWith('local-') ? undefined : conv.id,
      ...buildChatScopeBody(activeScope.value),
      chat_mode: chatMode.value,
    },
    assistantMsgId: aiTempId,
    getAssistantMsg: () => messages.value.find((m) => m.id === aiTempId),
    onUnauthorized: () => {
      messages.value = messages.value.filter((m) => m.id !== userTempId && m.id !== aiTempId)
    },
    onMeta: (data) => {
      if (!data.conversation_id) return
      if (draftConversationId.value && conv.id === draftConversationId.value) {
        const idx = conversations.value.findIndex((c) => c.id === conv.id)
        if (idx >= 0) {
          const title = q.length > 24 ? `${q.slice(0, 24)}…` : q
          const updated: Conversation = {
            ...conversations.value[idx],
            id: data.conversation_id,
            title: conversations.value[idx].title || title,
            updated_at: new Date().toISOString(),
            kb_id: selectedKb.value?.id,
          }
          conversations.value.splice(idx, 1, updated)
          currentConversation.value = updated
          draftConversationId.value = null
        }
      }
    },
    onChunk: () => queueMicrotask(scrollToBottom),
  })

  if (result === 'unauthorized') return
}

const newChat = () => {
  errorText.value = ''
  draftConversationId.value = null
  clearSelectedConversation()
  activeScope.value = { scope_type: 'kb' }
}


onMounted(() => {
  void loadKnowledgeBases()
  void loadConversations()
})

onUnmounted(() => {
  abortChatStream()
})
</script>

<style scoped>
.main-container {
  display: flex;
  flex: 1;
  min-height: 0;
  background: #f5f5f5;
}

.sidebar-left {
  width: 64px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  gap: 8px;
  transition: width 0.3s ease;
}

.new-chat-btn {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  background: #fff;
  color: #333;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.new-chat-btn:hover {
  background: #f7f7f7;
}

.new-chat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.new-chat-text {
  display: none;
  font-size: 13px;
  white-space: nowrap;
}

.sidebar-left:not(.collapsed) {
  /* 与知识库页侧边栏（KbSidebarTree）宽度保持一致 */
  width: 260px;
  align-items: stretch;
  padding: 12px 10px;
}

.sidebar-left:not(.collapsed) .nav-item,
.sidebar-left:not(.collapsed) .new-chat-btn {
  width: 100%;
  flex-direction: row;
  justify-content: flex-start;
  padding: 0 12px;
}

.sidebar-left:not(.collapsed) .nav-item span,
.sidebar-left:not(.collapsed) .new-chat-text {
  display: inline;
}

.sidebar-left:not(.collapsed) .nav-item svg {
  margin-right: 8px;
}

.sidebar-left.collapsed {
  width: 0;
  overflow: hidden;
  padding: 0;
  border-right: none;
}

.nav-item {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  color: #666;
  font-size: 12px;
  background: transparent;
  border: none;
}

.nav-item:hover {
  background: #f5f5f5;
}

.nav-item.active {
  color: var(--dp-primary);
}

.nav-item svg {
  width: 20px;
  height: 20px;
}

.sidebar-section {
  margin-top: 8px;
  border-top: 1px solid #f0f0f0;
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.sidebar-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 8px;
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: #f5f5f5;
}

.search-box {
  padding: 0 10px 10px;
}

.search-input {
  width: 100%;
  height: 34px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 0 10px;
  font-size: 13px;
  outline: none;
  color: #6b7280;
  background: #fff;
}

.search-input:focus {
  border-color: var(--dp-primary);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 8px;
}

.history-item {
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.history-item:hover {
  background: #f5f5f5;
}

.history-item.active {
  background: var(--dp-primary-bg);
}

.history-question {
  flex: 1;
  font-size: 13px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
}

.history-item:hover .history-delete-btn {
  opacity: 1;
}

.history-delete-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #f56c6c;
}

.history-empty {
  padding: 10px;
  font-size: 12px;
  color: #94a3b8;
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

.chat-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fff;
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

.chat-input {
  padding: 16px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
  display: flex;
  justify-content: center;
}

.home-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  padding: 40px;
}

.home-logo {
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.home-title {
  font-size: 32px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 8px;
  letter-spacing: 0.2px;
  line-height: 1.1;
  position: relative;

  animation:
    dp-title-float 3.2s ease-in-out infinite;
  will-change: transform, filter;
  filter: drop-shadow(0 10px 22px rgba(0, 0, 0, 0.08));
}

.home-subtitle {
  font-size: 16px;
  color: #999;
  margin-bottom: 40px;
  position: relative;
  animation: dp-subtitle-in 720ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
  opacity: 0.98;
}

.home-subtitle::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -10px;
  width: min(240px, 82%);
  height: 2px;
  transform: translateX(-50%);
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(17, 24, 39, 0), rgba(17, 24, 39, 0.65), rgba(17, 24, 39, 0));
  opacity: 0.9;
  animation: dp-underline 2.8s ease-in-out infinite;
}

@keyframes dp-title-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}

@keyframes dp-subtitle-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes dp-underline {
  0%,
  100% {
    opacity: 0.55;
    transform: translateX(-50%) scaleX(0.92);
  }
  50% {
    opacity: 1;
    transform: translateX(-50%) scaleX(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-title,
  .home-subtitle,
  .home-subtitle::after {
    animation: none !important;
  }
}

.ai-input-bar {
  /* 让输入区域占满一行，然后用 flex 精确居中内部输入框 */
  width: 100%;
  padding: 20px 0;
  /* 外层不铺白底，避免左右出现大块空白“白条” */
  border-top: none;
  background: transparent;
  display: flex;
  justify-content: center;
  margin-top: 40px;
  position: relative;
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
  color: #999;
  margin-bottom: 2px;
}

.kb-item-name {
  font-size: 14px;
  color: #333;
}
.dialog-input-shell {
  width: 100%;
  /* 宽度由外层 composer-wrap 控制，这里占满即可 */
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

.composer-wrap{
  position: relative;
  /* 以 home-content 的内容宽度为基准居中 */
  width: min(720px, 92%);
}

.dialog-input-main-row {
  display: flex;
  align-items: stretch;
}

.dialog-input-main{
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  color: #e91515;
  font-size: 14px;

  resize: none;          /* 不要右下角拖拽 */
  line-height: 22px;     /* 决定“初始扁不扁” */
  padding: 2px 6px;      /* 更像参考图的内边距 */
  min-height: 22px;      /* 1 行的最小高度 */
  max-height: 120px;     /* 超过这个高度就内部滚动 */
  overflow-y: auto;

  /* 关键：长串无空格字符也能换行，从而触发高度增长 */
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.dialog-input-main::placeholder {
  color: #bfbfbf;
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
  align-items: center;
  gap: 8px;
}

.dialog-pill {
  padding: 4px 10px;
  border-radius: 999px;
  border: none;
  background: #f7f7f7;
  font-size: 12px;
  color: #666;
  cursor: pointer;
}

.dialog-pill:hover{
  background: #efefef;
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
  color: #666;
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

.dialog-send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.dialog-send-btn:hover:not(:disabled) {
  background: var(--dp-primary-hover);
}

@keyframes float1 {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-6px); }
}

@keyframes float2 {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(5px) rotate(-3deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 1; transform: translate(-50%, -50%) scale(1.6); }
}
</style>