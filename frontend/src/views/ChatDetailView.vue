<template>
  <div class="page-root">
    <div class="chat-topbar">
      <button class="back-btn" @click="goBack" title="返回">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
      <div class="chat-title">
        <div class="chat-kb">@{{ kbName || '知识库' }}</div>
        <div class="chat-sub">{{ conversationId ? '会话中' : '新会话' }}</div>
      </div>
      <div class="chat-topbar-right"></div>
    </div>

    <div ref="chatContent" class="chat-content">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message"
        :class="[msg.role === 'assistant' ? 'ai' : 'user', msg.kind === 'hint' ? 'hint' : '']"
      >
        <div class="message-body">
          <ThinkingSection
            v-if="msg.role === 'assistant'"
            :text="msg.thinking"
          />
          <ChatThinkingPlaceholder
            v-if="isAssistantAwaitingContent(msg, streamingAssistantId)"
          />
          <div v-else class="message-text">{{ msg.content }}</div>
          <div class="message-meta">
            <span>{{ msg.role === 'assistant' ? '系统' : '用户' }} · {{ formatTime(msg.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-footer">
      <div class="composer-wrap">
        <ComposerBox
          v-model="questionInput"
          shell-variant="card"
          :enable-kb-picker="false"
          :disabled-send="!questionInput.trim() || isStreaming"
          :show-error-banner="false"
          placeholder="基于知识库提问"
          @send="sendQuestion"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import ComposerBox from '../components/ComposerBox.vue'
import ChatThinkingPlaceholder from '../components/ChatThinkingPlaceholder.vue'
import ThinkingSection from '../components/ThinkingSection.vue'
import { CHAT_STREAM_URL } from '../api/chat'
import { readChatSse, type ChatStreamPayload } from '../api/chatStream'
import { applyChatStreamToAssistant } from '../api/chatStreamHandlers'
import { useChatMode } from '../composables/useChatMode'
import { applyFetchUnauthorized } from '../auth/session'
import { isAbortError } from '../utils/errors'
import { isAssistantAwaitingContent } from '../utils/chatPending'

type ViewName = 'home' | 'kb' | 'history' | 'chat'
type ChatMsg = {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  created_at: string
  kind?: 'hint'
}

const { chatMode } = useChatMode()

const emit = defineEmits<{
  (e: 'navigate', view: ViewName): void
}>()

const chatContent = ref<HTMLElement | null>(null)
const kbId = ref<string>('')
const kbName = ref<string>('')
const conversationId = ref<string | null>(null)
const messages = ref<ChatMsg[]>([])
const questionInput = ref('')
const isStreaming = ref(false)
const streamingAssistantId = ref<string | null>(null)
let streamCtrl: AbortController | null = null

const formatTime = (dateStr: string) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatContent.value) chatContent.value.scrollTop = chatContent.value.scrollHeight
}

const pushHint = async (text: string) => {
  messages.value.push({
    id: `hint-${Date.now()}`,
    role: 'assistant',
    content: `提示：${text}`,
    created_at: new Date().toISOString(),
    kind: 'hint',
  })
  await scrollToBottom()
}

const goBack = () => {
  sessionStorage.removeItem('pendingChatFromHome')
  emit('navigate', 'home')
}

const sendQuestion = async () => {
  const q = questionInput.value.trim()
  if (!q || !kbId.value || isStreaming.value) return

  const userId = `u-${Date.now()}`
  const aiId = `a-${Date.now()}`
  messages.value.push(
    { id: userId, role: 'user', content: q, created_at: new Date().toISOString() },
    { id: aiId, role: 'assistant', content: '', created_at: new Date().toISOString() },
  )
  questionInput.value = ''
  isStreaming.value = true
  streamingAssistantId.value = aiId
  await scrollToBottom()

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
        kb_id: kbId.value,
        question: q,
        conversation_id: conversationId.value || undefined,
        chat_mode: chatMode.value,
      }),
    })

    if (res.status === 401) {
      applyFetchUnauthorized()
      messages.value = messages.value.filter((m) => m.id !== userId && m.id !== aiId)
      isStreaming.value = false
      return
    }

    if (!res.ok || !res.body) {
      let hint = '请求失败'
      try {
        const data = await res.json()
        hint = data?.user_hint || data?.message || hint
      } catch {}
      // 不落库：直接 UI 提示
      messages.value = messages.value.filter((m) => m.id !== aiId)
      await pushHint(hint === '知识库为空' ? '知识库为空,请先上传文档' : hint)
      return
    }
    let done = false
    await readChatSse(res, {
      onPayload: async (data: ChatStreamPayload) => {
        if (done) return

        if (data.event === 'meta' && data.conversation_id) {
          if (!conversationId.value) conversationId.value = data.conversation_id
          return
        }

        if (data.event === 'error' || data.code) {
          messages.value = messages.value.filter((m) => m.id !== aiId)
          await pushHint(String(data.content || '处理失败'))
          done = true
          return
        }

        if (data.content) {
          const aiMsg = messages.value.find((m) => m.id === aiId)
          if (aiMsg) {
            applyChatStreamToAssistant(data, aiMsg)
            await scrollToBottom()
          }
        }

        if (data.finished) {
          if (data.conversation_id && !conversationId.value) conversationId.value = data.conversation_id
          done = true
        }
      },
    })
  } catch (e) {
    if (isAbortError(e)) {
      return
    }
    console.error('stream failed:', e)
    messages.value = messages.value.filter((m) => m.id !== aiId)
    await pushHint('请求失败，请稍后重试')
  } finally {
    isStreaming.value = false
    streamingAssistantId.value = null
    streamCtrl = null
  }
}

onMounted(async () => {
  const raw = sessionStorage.getItem('pendingChatFromHome')
  if (!raw) {
    await pushHint('请从首页选择知识库后发起提问')
    return
  }
  let data: Record<string, unknown> = {}
  try {
    const parsed = JSON.parse(raw) as unknown
    if (parsed && typeof parsed === 'object') {
      data = parsed as Record<string, unknown>
    }
  } catch {
    data = {}
  }
  kbId.value = String(data.kbId || '')
  kbName.value = String(data.kbName || '')
  const firstQuestion = String(data.question || '').trim()
  if (firstQuestion) {
    questionInput.value = firstQuestion
    await sendQuestion()
  }
})

onUnmounted(() => {
  if (streamCtrl) {
    streamCtrl.abort()
    streamCtrl = null
  }
})
</script>

<style scoped>
.page-root {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.chat-topbar {
  height: 48px;
  display: grid;
  grid-template-columns: 48px 1fr 48px;
  align-items: center;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
}

.back-btn {
  width: 36px;
  height: 36px;
  margin-left: 8px;
  border-radius: 10px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #333;
}

.back-btn:hover {
  background: #f5f5f5;
}

.chat-title {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.1;
}

.chat-kb {
  font-size: 14px;
  color: #111;
  font-weight: 600;
  max-width: 70vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-sub {
  font-size: 12px;
  color: #999;
}

.chat-content {
  flex: 1;
  overflow-y: auto;
  padding: 18px 16px 12px;
  background: #fff;
}

.message {
  display: flex;
  margin: 10px 0;
}

.message.user {
  justify-content: flex-end;
}

.message.ai {
  justify-content: flex-start;
}

.message-body {
  max-width: min(720px, 92%);
  border-radius: 12px;
  padding: 10px 12px;
  border: 1px solid #f0f0f0;
  background: #fafafa;
}

.message.user .message-body {
  background: var(--dp-primary);
  color: #fff;
  border-color: var(--dp-primary);
}

.message.hint .message-body {
  background: #fff7e6;
  border-color: #ffd591;
  color: #ad4e00;
}

.message-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  font-size: 14px;
  line-height: 22px;
}

.message-meta {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.message.user .message-meta {
  color: rgba(255, 255, 255, 0.85);
}

.chat-footer {
  padding: 14px 0 18px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: center;
}

.composer-wrap {
  width: min(820px, 94%);
}
</style>

