<template>
  <AppShell @toggle-sidebar="toggleSidebar">
    <template #nav-left>
      <button class="top-collapse-btn" type="button" title="收起侧边栏" @click="toggleSidebar">
        <IconChevronLeft />
      </button>
      <button class="top-back-btn" type="button" title="返回" @click="goHome">
        <MascotLogo :size="28" />
      </button>
    </template>

    <div class="main-container">
      <ChatSidebar
        variant="history"
        :collapsed="sidebarCollapsed"
        :conversations="filteredConversations"
        :active-conversation-id="currentConversation?.id ?? null"
        v-model:search-text="searchText"
        search-placeholder="搜索历史会话..."
        @new-chat="newChat"
        @select="selectConversation"
        @delete="handleDeleteConversation"
        @refresh="loadConversations"
        @go-kb="goKb"
      />

      <ChatPanel
        ref="chatPanelRef"
        :title="`${scopeDisplayLabel(activeScope)} · ${currentConversation?.title || '会话详情'}`"
        :messages="displayMessages"
        :pending-assistant-id="streamingAssistantId"
        :empty="!currentConversation"
      >
        <template #empty>
          <div class="chat-empty">请选择一条问答历史查看详情</div>
        </template>
        <template #composer>
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
            <AttachmentChip
              :name="selectedAttachmentName || undefined"
              @remove="clearAttachment"
            />
          </div>
        </template>
      </ChatPanel>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { scopeDisplayLabel } from '../api/chatScope'
import AppShell from '../components/AppShell.vue'
import AttachmentChip from '../components/AttachmentChip.vue'
import ChatPanel from '../components/chat/ChatPanel.vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import ComposerBox from '../components/ComposerBox.vue'
import IconChevronLeft from '../components/icons/IconChevronLeft.vue'
import MascotLogo from '../components/MascotLogo.vue'
import { useAppNavigation } from '../composables/useAppNavigation'
import { useConversationChat } from '../composables/useConversationChat'

const route = useRoute()
const { goHome, goKb } = useAppNavigation()

const sidebarCollapsed = ref(false)
const searchText = ref('')
const questionInput = ref('')
const selectedAttachmentName = ref('')
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)

const {
  currentConversation,
  activeScope,
  errorText,
  kbOptions,
  isStreaming,
  streamingAssistantId,
  displayMessages,
  chatInputPlaceholder,
  chatKbId,
  loadKnowledgeBases,
  loadConversations,
  selectConversation,
  handleDeleteConversation,
  sendMessage,
  newChat,
  filterConversations,
  openConversationById,
  abortChatStream,
} = useConversationChat({
  mode: 'history',
  onScroll: () => chatPanelRef.value?.scrollToBottom(),
  onFileScopeNavigate: goKb,
})

const filteredConversations = computed(() => filterConversations(searchText))

const openAttachmentDialog = () => {
  errorText.value = '附件功能尚未接入'
}

const clearAttachment = () => {
  selectedAttachmentName.value = ''
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const sendQuestion = async () => {
  const q = questionInput.value.trim()
  if (!q) return
  const sent = await sendMessage(q)
  if (sent) questionInput.value = ''
}

onMounted(() => {
  void (async () => {
    await loadKnowledgeBases()
    await loadConversations()
    await openConversationById(typeof route.query.id === 'string' ? route.query.id : null)
  })()
})

watch(
  () => route.query.id,
  (id) => {
    void openConversationById(typeof id === 'string' ? id : null)
  },
)

onUnmounted(() => {
  abortChatStream()
})
</script>

<style scoped>
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

.main-container {
  display: flex;
  flex: 1;
  min-height: 0;
  background: #f5f5f5;
}

.chat-empty {
  padding: 18px 12px;
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
}

.composer-wrap {
  position: relative;
  width: min(720px, 92%);
}
</style>
