<template>
  <div class="content-area">
    <div v-if="title" class="chat-header">
      <div class="chat-title">{{ title }}</div>
    </div>
    <div ref="chatContentRef" class="chat-content">
      <slot v-if="empty" name="empty" />
      <ChatMessageList
        v-else
        variant="page"
        :messages="messages"
        :pending-assistant-id="pendingAssistantId"
      />
    </div>
    <div class="chat-input">
      <slot name="composer" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import ChatMessageList, { type ChatModalMessage } from '../ChatMessageList.vue'

defineProps<{
  title?: string
  messages: ChatModalMessage[]
  pendingAssistantId?: string | null
  empty?: boolean
}>()

const chatContentRef = ref<HTMLElement | null>(null)

const scrollToBottom = () => {
  if (chatContentRef.value) {
    chatContentRef.value.scrollTop = chatContentRef.value.scrollHeight
  }
}

defineExpose({ scrollToBottom })
</script>

<style scoped>
.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  min-width: 0;
}

.chat-header {
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
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
  min-height: 0;
}

.chat-input {
  padding: 16px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

.chat-empty {
  color: #94a3b8;
  font-size: 14px;
  text-align: center;
  padding: 48px 16px;
}
</style>
