<template>
  <div class="chat-modal-mask" :class="{ embedded: expanded }" @click.self="emit('close')">
    <div class="chat-modal" :class="{ expanded: expanded }">
      <div class="chat-modal-header">
        <div class="chat-modal-title">{{ modalTitle }}</div>
        <div class="chat-modal-actions">
          <button class="chat-modal-icon-btn" title="新建会话" type="button" @click="emit('newConversation')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <button class="chat-modal-icon-btn" title="查看历史" type="button" @click="emit('toggleHistory')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </button>
          <button class="chat-modal-icon-btn" title="放大/还原" type="button" @click="emit('toggleExpand')">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <g v-if="expanded">
                <!-- 还原（缩小）：对角箭头朝内 -->
                <line x1="20" y1="4" x2="14" y2="10" />
                <polyline points="16 10 14 10 14 8" />

                <line x1="4" y1="20" x2="10" y2="14" />
                <polyline points="8 14 10 14 10 16" />
              </g>
              <g v-else>
                <!-- 进入全屏（放大）：四角展开 -->
                <path d="M8 3H5a2 2 0 0 0-2 2v3" />
                <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
                <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
                <path d="M3 16v3a2 2 0 0 0 2 2h3" />
              </g>
            </svg>
          </button>
          <button class="chat-modal-icon-btn" title="关闭" type="button" @click="emit('close')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>
      <div class="chat-modal-main">
        <div class="chat-modal-body">
          <ChatMessageList
            :messages="messages"
            :pending-assistant-id="pendingAssistantId"
          />
        </div>
        <div v-if="showHistory" class="chat-history-panel">
          <div class="chat-history-title">问答历史</div>
          <div class="chat-history-list">
            <div v-for="group in conversationGroups" :key="group.label" class="chat-history-group">
              <div class="chat-history-group-title">{{ group.label }}</div>
              <button
                v-for="c in group.items"
                :key="c.id"
                type="button"
                class="chat-history-item"
                :class="{ active: c.id === activeConversationId }"
                @click="emit('selectConversation', c.id)"
              >
                <span class="chat-history-time">{{ formatHistoryTime(c.updated_at) }}</span>
                <span class="chat-history-content">
                  <span class="chat-history-text">{{ c.title || '新会话' }}</span>
                </span>
                <span class="chat-history-menu-wrap" @click.stop>
                  <button class="chat-history-menu-btn" type="button" title="更多操作" @click="emit('toggleConversationMenu', c.id)">
                    ⋯
                  </button>
                  <div v-if="openConversationMenuId === c.id" class="chat-history-menu">
                    <button type="button" class="chat-history-menu-item" @click="emit('renameConversation', c)">重命名</button>
                    <button type="button" class="chat-history-menu-item danger" @click="emit('deleteConversation', c.id)">
                      删除
                    </button>
                  </div>
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
      <div class="chat-modal-footer">
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
import ComposerBox from './ComposerBox.vue'
import ChatMessageList from './ChatMessageList.vue'
import type { ChatCitation, ChatModalMessage } from './ChatMessageList.vue'

export type { ChatCitation, ChatModalMessage }

export type ChatModalConversation = { id: string; title?: string | null; updated_at: string }

export type ChatModalConversationGroup = { label: string; items: ChatModalConversation[] }

const composerInput = defineModel<string>({ required: true })

defineProps<{
  modalTitle: string
  expanded: boolean
  showHistory: boolean
  messages: ChatModalMessage[]
  conversationGroups: ChatModalConversationGroup[]
  activeConversationId: string | null
  openConversationMenuId: string | null
  isStreaming: boolean
  pendingAssistantId?: string | null
  composerPlaceholder: string
}>()

const emit = defineEmits<{
  close: []
  newConversation: []
  toggleHistory: []
  toggleExpand: []
  selectConversation: [id: string]
  toggleConversationMenu: [id: string]
  renameConversation: [item: ChatModalConversation]
  deleteConversation: [id: string]
  send: []
  attachment: []
}>()

function formatHistoryTime(dateStr: string) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const hh = `${d.getHours()}`.padStart(2, '0')
  const mm = `${d.getMinutes()}`.padStart(2, '0')
  return `${hh}:${mm}`
}
</script>

<style scoped>
.chat-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
}

.chat-modal-mask.embedded {
  position: absolute;
  inset: 0;
  background: #fff;
  display: block;
  z-index: 50;
}

.chat-modal {
  width: min(900px, 92vw);
  height: min(78vh, 760px);
  background: #fff;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-modal-mask.embedded .chat-modal {
  width: 100%;
  height: 100%;
  border-radius: 0;
  box-shadow: none;
}

.chat-modal.expanded {
  width: min(1280px, 98vw);
  height: min(92vh, 980px);
}

.chat-modal-header {
  height: 48px;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.chat-modal-title {
  font-size: 14px;
  font-weight: 600;
  color: #6b7280;
}

.chat-modal-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.chat-modal-icon-btn {
  border: none;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: #f5f5f5;
  cursor: pointer;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  line-height: 0;
}

.chat-modal-icon-btn svg {
  display: block;
}

.chat-modal-icon-btn:hover {
  background: var(--dp-primary-bg);
  color: var(--dp-primary);
}

.chat-modal-main {
  flex: 1;
  display: flex;
  min-height: 0;
}

.chat-modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.chat-history-panel {
  width: 260px;
  border-left: 1px solid #eee;
  background: #fafafa;
  display: flex;
  flex-direction: column;
}

.chat-history-title {
  padding: 12px 12px 8px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
}

.chat-history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-history-group {
  border-top: 1px solid #ececec;
  padding-top: 8px;
}

.chat-history-group:first-child {
  border-top: none;
  padding-top: 0;
}

.chat-history-group-title {
  padding: 2px 4px 8px;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.chat-history-item {
  border: none;
  background: transparent;
  border-radius: 6px;
  text-align: left;
  padding: 6px 8px;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
  display: grid;
  grid-template-columns: 42px 1fr 28px;
  align-items: start;
  gap: 6px;
  position: relative;
}

.chat-history-item.active {
  background: #f0f0f0;
}

.chat-history-item:hover {
  background: #f5f5f5;
}

.chat-history-time {
  font-size: 12px;
  color: #94a3b8;
}

.chat-history-text {
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-history-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.chat-history-menu-wrap {
  position: relative;
}

.chat-history-menu-btn {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
}

.chat-history-menu-btn:hover {
  background: #ececec;
  color: #6b7280;
}

.chat-history-menu {
  position: absolute;
  top: 24px;
  right: 0;
  width: 130px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.16);
  padding: 6px;
  z-index: 30;
}

.chat-history-menu-item {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 13px;
  color: #6b7280;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.chat-history-menu-item:hover {
  background: #f5f5f5;
}

.chat-history-menu-item.danger {
  color: #d4380d;
}

.chat-modal-footer {
  border-top: none;
  padding: 10px 12px 40px;
  display: flex;
  justify-content: center;
  background: transparent;
}

.modal-input-shell {
  width: 100%;
  max-width: 720px;
  margin: 0 auto 2cm;
  min-height: 56px;
  transform: none;
}

.chat-modal-mask.embedded .chat-modal-footer {
  padding: 20px 32px;
  border-top: none;
  background: #fff;
  justify-content: center;
  transform: translateY(-1cm);
}

.chat-modal-mask.embedded .modal-input-shell {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  min-height: auto;
}

.chat-modal-input {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 8px 10px;
  outline: none;
}

.chat-modal-send {
  border: none;
  border-radius: 8px;
  background: var(--dp-primary);
  color: #fff;
  padding: 0 14px;
  cursor: pointer;
}

.chat-modal-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
