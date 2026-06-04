<template>
  <div class="chat-modal-mask" :class="{ embedded: expanded }" @click.self="emit('close')">
    <div class="chat-modal" :class="{ expanded: expanded }">
      <div class="chat-modal-header">
        <div class="chat-modal-title">{{ modalTitle }}</div>
        <div class="chat-modal-actions">
          <button class="chat-modal-icon-btn" title="新建会话" type="button" @click="emit('newConversation')">
            <IconPlus :size="14" :stroke-width="1.5" />
          </button>
          <button class="chat-modal-icon-btn" title="查看历史" type="button" @click="emit('toggleHistory')">
            <IconClock :size="14" :stroke-width="1.5" />
          </button>
          <button class="chat-modal-icon-btn" title="放大/还原" type="button" @click="emit('toggleExpand')">
            <IconExpand :expanded="expanded" />
          </button>
          <button class="chat-modal-icon-btn" title="关闭" type="button" @click="emit('close')">
            <IconClose :size="14" />
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
import IconClock from './icons/IconClock.vue'
import IconClose from './icons/IconClose.vue'
import IconExpand from './icons/IconExpand.vue'
import IconPlus from './icons/IconPlus.vue'
import type { ChatModalMessage } from './ChatMessageList.vue'
import type { ChatCitation } from '../api/chatTypes'

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
