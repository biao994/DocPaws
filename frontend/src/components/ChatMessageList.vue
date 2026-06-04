<template>
  <div class="chat-message-list" :class="variantClass">
    <div v-for="msg in messages" :key="msg.id" class="modal-message" :class="msg.role">
      <ThinkingSection
        v-if="msg.role === 'assistant'"
        :text="msg.thinking"
      />
      <ChatThinkingPlaceholder
        v-if="isAssistantAwaitingContent(msg, pendingAssistantId)"
      />
      <div v-else class="modal-message-text">{{ msg.content }}</div>
      <div v-if="msg.role === 'assistant' && msg.citations?.length" class="modal-citations">
        <div class="source-title">引用来源</div>
        <div v-for="c in msg.citations" :key="`${msg.id}-${c.chunk_id}`" class="source-item">
          <div class="source-icon">
            <IconFile />
          </div>
          <div>
            <div>{{ c.source || '文档片段' }} <span v-if="c.page_no">· 第{{ c.page_no }}页</span></div>
            <div class="source-snippet">{{ c.snippet }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import ChatThinkingPlaceholder from './ChatThinkingPlaceholder.vue'
import IconFile from './icons/IconFile.vue'
import ThinkingSection from './ThinkingSection.vue'
import { isAssistantAwaitingContent } from '../utils/chatPending'
import type { ChatCitation } from '../api/chatTypes'

export type { ChatCitation } from '../api/chatTypes'

export type ChatModalMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  citations?: ChatCitation[]
}

const props = withDefaults(
  defineProps<{
    messages: readonly ChatModalMessage[]
    pendingAssistantId?: string | null
    variant?: 'modal' | 'page'
  }>(),
  { variant: 'modal' },
)

const variantClass = computed(() =>
  props.variant === 'page' ? 'chat-message-list--page' : '',
)
</script>

<style scoped>
.modal-message {
  margin-bottom: 14px;
}

.modal-message.user {
  text-align: right;
}

.modal-message-text {
  display: inline-block;
  max-width: 76%;
  text-align: left;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f5f5f5;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.modal-message.user .modal-message-text {
  background: var(--dp-primary-bg);
}

.modal-citations {
  margin-top: 8px;
  text-align: left;
}

.source-title {
  font-size: 12px;
  color: #999;
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
  flex-shrink: 0;
  color: #666;
}

.source-snippet {
  font-size: 12px;
  color: #999;
}

/* 主聊天页（Home / History）样式 */
.chat-message-list--page .modal-message {
  margin-bottom: 16px;
}

.chat-message-list--page .modal-message.user .modal-message-text {
  background: var(--dp-primary);
  color: #fff;
}

.chat-message-list--page .modal-message-text {
  max-width: min(720px, 70vw);
}
</style>
