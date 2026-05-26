import { computed, ref, watch } from 'vue'

export type ChatMode = 'fast' | 'deep'

const STORAGE_KEY = 'docpaws_chat_mode'

function readStoredMode(): ChatMode {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'fast' || v === 'deep') return v
  } catch {
    /* ignore */
  }
  return 'fast'
}

const chatMode = ref<ChatMode>(readStoredMode())

watch(chatMode, (m) => {
  try {
    localStorage.setItem(STORAGE_KEY, m)
  } catch {
    /* ignore */
  }
})

export function useChatMode() {
  const chatModeLabel = computed(() =>
    chatMode.value === 'deep' ? 'DS 深度' : 'DS 快速',
  )

  const toggleChatMode = () => {
    chatMode.value = chatMode.value === 'fast' ? 'deep' : 'fast'
  }

  return {
    chatMode,
    chatModeLabel,
    toggleChatMode,
    setChatMode: (m: ChatMode) => {
      chatMode.value = m
    },
  }
}
