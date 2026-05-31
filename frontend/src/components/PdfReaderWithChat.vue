<template>
  <div class="reader-page">
    <div class="reader-main">
      <div class="reader-topbar">
        <div class="reader-title" :title="documentTitle || undefined">{{ documentTitle }}</div>
        <button type="button" class="reader-close" title="关闭" @click="emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <iframe class="reader-frame" :src="pdfSrc" title="文件预览" scrolling="no"></iframe>
    </div>
    <div class="reader-chat">
      <div class="reader-chat-header">对话</div>
      <div class="reader-chat-body">
        <ChatMessageList
          :messages="messages"
          :pending-assistant-id="pendingAssistantId"
        />
      </div>
      <div class="reader-chat-footer">
        <ComposerBox
          v-model="composerInput"
          shell-variant="card"
          :enable-kb-picker="false"
          :disabled-send="isStreaming || !composerInput.trim()"
          :show-error-banner="false"
          :placeholder="composerPlaceholder"
          @send="emit('send')"
          @attachment="emit('attachment')"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ChatMessageList from './ChatMessageList.vue'
import ComposerBox from './ComposerBox.vue'
import type { ChatModalMessage } from './ChatMessageList.vue'

const composerInput = defineModel<string>({ required: true })

defineProps<{
  pdfSrc: string
  documentTitle?: string
  messages: ChatModalMessage[]
  isStreaming: boolean
  pendingAssistantId?: string | null
  composerPlaceholder: string
}>()

const emit = defineEmits<{
  close: []
  send: []
  attachment: []
}>()
</script>

<style scoped>
.reader-page {
  flex: 1;
  display: flex;
  min-height: 0;
}

.reader-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.reader-topbar {
  height: 50px;
  min-height: 50px;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  gap: 8px;
}

.reader-title {
  flex: 1;
  min-width: 0;
  text-align: left;
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reader-close {
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  flex-shrink: 0;
}

.reader-close:hover {
  background: #f5f5f5;
  color: #6b7280;
}

.reader-frame {
  flex: 1;
  width: 100%;
  border: none;
  background: #f5f5f5;
}

.reader-chat {
  width: 320px;
  border-left: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.reader-chat-header {
  height: 50px;
  min-height: 50px;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 600;
}

.reader-chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 10px 0;
}

.reader-chat-footer {
  padding: 8px 8px 44px;
}
</style>
