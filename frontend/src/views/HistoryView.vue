<template>
  <div class="page-root">
    <!-- 顶部导航栏（复用 HomeView） -->
    <div class="top-nav">
      <div class="nav-left">
        <button class="top-collapse-btn" @click="toggleSidebar" title="收起侧边栏">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>
        <button class="top-back-btn" @click="navigate('home')" title="返回">
          <MascotLogo :size="28" />
        </button>
      </div>
      <div class="nav-actions" style="position: relative">
        <div ref="userInfo" class="user-info" @click.stop="toggleSettings">
          <div class="user-avatar">{{ avatarLetter }}</div>
          <span class="user-name">{{ userDisplayName }}</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        <div ref="settingsMenu" class="settings-menu" :class="{ show: showSettings }">
          <template v-if="false">
            <div class="settings-item">提交反馈</div>
            <div class="settings-divider"></div>
          </template>
          <div class="settings-item logout" @click.stop="handleLogout">退出登录</div>
        </div>
      </div>
    </div>

    <!-- 主布局：三栏 -->
    <div class="main-container">
      <!-- 左侧：导航 + 问答历史（默认展开，符合图一） -->
      <div class="sidebar-left" :class="{ collapsed: sidebarCollapsed }">
        <button class="new-chat-btn" @click="newChat" title="新建会话">
          <span class="new-chat-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"></path>
              <line x1="12" y1="8.5" x2="12" y2="13.5"></line>
              <line x1="9.5" y1="11" x2="14.5" y2="11"></line>
            </svg>
          </span>
          <span class="new-chat-text">新建会话</span>
        </button>

        <button class="nav-item" @click="navigate('kb')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
          <span>知识库</span>
        </button>
        <button class="nav-item active">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
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
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                  <path d="M10 11v6"></path>
                  <path d="M14 11v6"></path>
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path>
                </svg>
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
          <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role === 'assistant' ? 'ai' : 'user'">
            <div class="message-body">
              <ThinkingSection
                v-if="msg.role === 'assistant'"
                :text="msg.thinking"
              />
              <div class="message-text">{{ msg.content }}</div>
              <div class="message-meta">
                <span>{{ msg.role === 'assistant' ? '系统' : '用户' }} · {{ formatTime(msg.created_at) }}</span>
              </div>
            </div>
          </div>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import ComposerBox from '../components/ComposerBox.vue'
import ThinkingSection from '../components/ThinkingSection.vue'
import MascotLogo from '../components/MascotLogo.vue'
import { logout as authLogout } from '../api/auth'
import { readChatSse, type ChatStreamPayload } from '../api/chatStream'
import { applyChatStreamToAssistant } from '../api/chatStreamHandlers'
import { useChatMode } from '../composables/useChatMode'
import { listKnowledgeBases } from '../api/kb'
import { deleteConversation, getConversation, listConversationsPaged } from '../api/conversations'
import {
  buildChatScopeBody,
  scopeDisplayLabel,
  scopeFromConversation,
  scopeInputPlaceholder,
  type ChatScopePayload,
} from '../api/chatScope'
import { CHAT_STREAM_URL } from '../api/chat'
import { applyFetchUnauthorized, clearSession, currentUser } from '../auth/session'
import { isAbortError } from '../utils/errors'
import { applyKbMentionToInput } from '../utils/kbMention'
import { setOpenFileChat } from '../utils/openFileChat'

type ViewName = 'home' | 'kb' | 'history' | 'chat'
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
  role: string
  content: string
  thinking?: string
  created_at: string
}

const { chatMode } = useChatMode()



const emit = defineEmits<{
  (e: 'navigate', view: ViewName): void
}>()

const userDisplayName = computed(
  () => currentUser.value?.username || currentUser.value?.email || '用户',
)
const avatarLetter = computed(() => {
  const n = userDisplayName.value.trim()
  return n ? n.charAt(0).toUpperCase() : 'U'
})

const handleLogout = async () => {
  showSettings.value = false
  try {
    await authLogout()
  } catch {
    /* noop */
  }
  clearSession()
}

const sidebarCollapsed = ref(false)
const showSettings = ref(false)
const searchText = ref('')
const kbOptions = ref<KbOption[]>([])
const selectedKb = ref<KbOption | null>(null)
const conversations = ref<Conversation[]>([])
const currentConversation = ref<Conversation | null>(null)
const messages = ref<Message[]>([])
const questionInput = ref('')
const isStreaming = ref(false)
const errorText = ref('')
const selectedAttachmentName = ref('')
let streamCtrl: AbortController | null = null
const activeScope = ref<ChatScopePayload>({ scope_type: 'kb' })
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

const toggleSettings = () => {
  showSettings.value = !showSettings.value
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
  isStreaming.value = true
  errorText.value = ''
  scrollToBottom()

  try {
    if (streamCtrl) {
      streamCtrl.abort()
      streamCtrl = null
    }
    streamCtrl = new AbortController()
    const res = await fetch(CHAT_STREAM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      signal: streamCtrl.signal,
      body: JSON.stringify({
        kb_id: kbIdForChat,
        question,
        conversation_id: currentConversation.value?.id?.startsWith('local-')
          ? undefined
          : currentConversation.value?.id,
        ...buildChatScopeBody(activeScope.value),
        chat_mode: chatMode.value,
      }),
    })

    if (res.status === 401) {
      applyFetchUnauthorized()
      messages.value = messages.value.filter((m) => m.id !== userTempId && m.id !== aiTempId)
      isStreaming.value = false
      return
    }

    if (!res.ok || !res.body) {
      let hint = '请求失败'
      try {
        const data = await res.json()
        hint = data?.user_hint || data?.message || hint
      } catch {}
      throw new Error(hint)
    }
    let done = false
    await readChatSse(res, {
      onPayload: async (payload: ChatStreamPayload) => {
        if (done) return
        if (payload.event === 'error' || payload.code) {
          throw new Error(String(payload.content || '处理失败'))
        }
        if (payload.content) {
          const aiMsg = messages.value.find((m) => m.id === aiTempId)
          if (aiMsg) {
            applyChatStreamToAssistant(payload, aiMsg)
            scrollToBottom()
          }
        }
        if (payload.finished) {
          done = true
        }
      },
    })
  


  } catch(e){
    if (isAbortError(e)) {
      return
    }
    console.error('发送失败:', e)
    const msg = e instanceof Error ? e.message : '发送失败，请稍后重试'
    const aiMsg = messages.value.find((m) => m.id === aiTempId)
    if (aiMsg) {
      aiMsg.content = `提示：${msg}`
    }
  } finally {
    isStreaming.value = false
    streamCtrl = null
  }
}
// 点击外部关闭下拉菜单
const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement | null
  if (!target) return
  
  if (settingsMenu.value && userInfo.value && !settingsMenu.value.contains(target) && !userInfo.value.contains(target)) {
    showSettings.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
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
  document.removeEventListener('click', handleClickOutside)
  if (streamCtrl) {
    streamCtrl.abort()
    streamCtrl = null
  }
})


</script>

<style scoped>
.page-root {
  height: 100vh;
  background: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

* {
  box-sizing: border-box;
}

.top-nav {
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  padding: 0 16px;
  justify-content: space-between;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

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

.nav-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}

.user-info:hover {
  background: #f5f5f5;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--dp-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 500;
}

.user-name {
  font-size: 14px;
  color: #6b7280;
}

.settings-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 8px;
  min-width: 180px;
  display: none;
  z-index: 100;
}

.settings-menu.show {
  display: block;
}

.settings-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #6b7280;
}

.settings-item:hover {
  background: #f5f5f5;
}

.settings-item.logout {
  color: #6b7280;
}

.settings-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 8px 0;
}

.main-container {
  display: flex;
  height: calc(100vh - 48px);
  position: relative;
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
  background: #fafafa;
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