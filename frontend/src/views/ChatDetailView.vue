<template>
  <div class="page-root">
    <div class="chat-topbar">
      <button class="back-btn" type="button" @click="goBack" title="返回">
        <IconChevronLeft />
      </button>
      <div class="chat-title">
        <div class="chat-kb">@{{ kbName || '知识库' }}</div>
        <div class="chat-sub">{{ conversationId ? '会话中' : '新会话' }}</div>
      </div>
      <div class="chat-topbar-right"></div>
    </div>

    <div ref="chatContent" class="chat-content">
      <ChatMessageList
        variant="page"
        :messages="displayMessages"
        :pending-assistant-id="streamingAssistantId"
      />
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
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

import ChatMessageList, { type ChatModalMessage } from '../components/ChatMessageList.vue'
import type { ChatCitation } from '../api/chatTypes'
import ComposerBox from '../components/ComposerBox.vue'
import IconChevronLeft from '../components/icons/IconChevronLeft.vue'
import { useChatMode } from '../composables/useChatMode'
import { useChatStream } from '../composables/useChatStream'
import { isAbortError } from '../utils/errors'

type ViewName = 'home' | 'kb' | 'history' | 'chat'
type ChatMsg = {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  citations?: ChatCitation[]
  created_at: string
  kind?: 'hint'
}

const { chatMode } = useChatMode()
const { isStreaming, streamingAssistantId, sendChatStream, abort: abortChatStream } = useChatStream()

const emit = defineEmits<{
  (e: 'navigate', view: ViewName): void
}>()

const chatContent = ref<HTMLElement | null>(null)
const kbId = ref<string>('')
const kbName = ref<string>('')
const conversationId = ref<string | null>(null)
const messages = ref<ChatMsg[]>([])
const questionInput = ref('')

const displayMessages = computed((): ChatModalMessage[] =>
  messages.value.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    thinking: m.thinking,
    citations: m.citations,
  })),
)

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
  await scrollToBottom()

  try {
    const result = await sendChatStream({
      body: {
        kb_id: kbId.value,
        question: q,
        conversation_id: conversationId.value || undefined,
        chat_mode: chatMode.value,
      },
      assistantMsgId: aiId,
      getAssistantMsg: () => messages.value.find((m) => m.id === aiId),
      inlineError: false,
      onUnauthorized: () => {
        messages.value = messages.value.filter((m) => m.id !== userId && m.id !== aiId)
      },
      onMeta: (data) => {
        if (data.conversation_id && !conversationId.value) {
          conversationId.value = data.conversation_id
        }
      },
      onError: (message) => {
        messages.value = messages.value.filter((m) => m.id !== aiId)
        void pushHint(message)
        return 'handled'
      },
      onChunk: () => void scrollToBottom(),
      onFinished: (data) => {
        if (data.conversation_id && !conversationId.value) {
          conversationId.value = data.conversation_id
        }
      },
    })

    if (result === 'failed' && !messages.value.some((m) => m.id === aiId)) {
      // HTTP 层失败且未走 onError
      return
    }
    if (result === 'failed') {
      const aiMsg = messages.value.find((m) => m.id === aiId)
      if (aiMsg && !aiMsg.content) {
        messages.value = messages.value.filter((m) => m.id !== aiId)
        await pushHint('请求失败，请稍后重试')
      }
    }
  } catch (e) {
    if (isAbortError(e)) return
    console.error('stream failed:', e)
    messages.value = messages.value.filter((m) => m.id !== aiId)
    await pushHint('请求失败，请稍后重试')
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
  abortChatStream()
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
