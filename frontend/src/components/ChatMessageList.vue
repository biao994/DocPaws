<template>
  <div class="chat-message-list">
    <div v-for="msg in messages" :key="msg.id" class="modal-message" :class="msg.role">
      <ThinkingSection
        v-if="msg.role === 'assistant'"
        :text="msg.thinking"
      />
      <div class="modal-message-text">{{ msg.content }}</div>
      <div v-if="msg.role === 'assistant' && msg.citations?.length" class="modal-citations">
        <div class="source-title">引用来源</div>
        <div v-for="c in msg.citations" :key="`${msg.id}-${c.chunk_id}`" class="source-item">
          <div class="source-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
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
import ThinkingSection from './ThinkingSection.vue'

export type ChatCitation = {
  chunk_id: string
  document_id?: string
  page_no?: number
  snippet: string
  source?: string
}

export type ChatModalMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  citations?: ChatCitation[]
}

defineProps<{
  messages: readonly ChatModalMessage[]
}>()
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
}

.source-snippet {
  font-size: 12px;
  color: #999;
}
</style>
