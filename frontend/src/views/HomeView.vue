<template>
  <AppShell @toggle-sidebar="toggleSidebar">
    <div class="main-container">
      <ChatSidebar
        variant="home"
        :collapsed="sidebarCollapsed"
        :conversations="filteredConversations"
        :active-conversation-id="currentConversation?.id ?? null"
        v-model:search-text="historySearchText"
        :show-search="showHistorySearch"
        search-placeholder="搜索对话历史..."
        @new-chat="newChat"
        @select="selectConversation"
        @delete="handleDeleteConversation"
        @toggle-search="toggleHistorySearch"
        @go-kb="goKb"
      />

      <ChatPanel
        v-if="currentConversation"
        ref="chatPanelRef"
        :title="`${scopeDisplayLabel(activeScope)} · ${currentConversation.title}`"
        :messages="displayMessages"
        :pending-assistant-id="streamingAssistantId"
      >
        <template #composer>
          <div class="composer-wrap">
            <ComposerBox
              v-model="inputValue"
              shell-variant="card"
              :enable-kb-picker="false"
              :kb-options="kbOptions"
              :selected-kb-id="chatKbId"
              :disabled-send="!chatKbId || !inputValue.trim()"
              :error-text="errorText"
              :show-error-banner="false"
              :placeholder="chatInputPlaceholder"
              @send="sendFromHome"
            />
          </div>
        </template>
      </ChatPanel>

      <div v-else class="content-area">
        <HomeWelcomeHero>
          <div class="composer-wrap">
            <ComposerBox
              v-model="inputValue"
              shell-variant="card"
              :kb-options="kbOptions"
              :selected-kb-id="selectedKb?.id ?? null"
              :disabled-send="!selectedKb || !inputValue.trim()"
              :error-text="errorText"
              :show-error-banner="false"
              :placeholder="chatInputPlaceholder"
              @send="sendFromHome"
              @select-kb="selectKb"
            />
          </div>
        </HomeWelcomeHero>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { scopeDisplayLabel } from '../api/chatScope'
import AppShell from '../components/AppShell.vue'
import ChatPanel from '../components/chat/ChatPanel.vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import HomeWelcomeHero from '../components/chat/HomeWelcomeHero.vue'
import ComposerBox from '../components/ComposerBox.vue'
import { useAppNavigation } from '../composables/useAppNavigation'
import { type KbOption, useConversationChat } from '../composables/useConversationChat'
import { applyKbMentionToInput } from '../utils/kbMention'

const { goKb } = useAppNavigation()

const sidebarCollapsed = ref(false)
const inputValue = ref('')
const showHistorySearch = ref(false)
const historySearchText = ref('')
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)

const {
  currentConversation,
  activeScope,
  errorText,
  kbOptions,
  selectedKb,
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
  abortChatStream,
} = useConversationChat({
  mode: 'home',
  onScroll: () => chatPanelRef.value?.scrollToBottom(),
  onFileScopeNavigate: goKb,
})

const filteredConversations = computed(() => filterConversations(historySearchText))

const toggleHistorySearch = () => {
  showHistorySearch.value = !showHistorySearch.value
  if (!showHistorySearch.value) {
    historySearchText.value = ''
  }
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const selectKb = (kb: KbOption) => {
  selectedKb.value = kb
  inputValue.value = applyKbMentionToInput(inputValue.value, kb.name)
}

const sendFromHome = async () => {
  const q = inputValue.value.trim()
  if (!q) return
  const sent = await sendMessage(q)
  if (sent) inputValue.value = ''
}

onMounted(() => {
  void loadKnowledgeBases()
  void loadConversations()
})

onUnmounted(() => {
  abortChatStream()
})
</script>

<style scoped>
.main-container {
  display: flex;
  flex: 1;
  min-height: 0;
  background: #f5f5f5;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.composer-wrap {
  position: relative;
  width: min(720px, 92%);
}
</style>
