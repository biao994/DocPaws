<template>
  <div class="sidebar-left" :class="{ collapsed, [`variant-${variant}`]: true }">
    <button class="new-chat-btn" type="button" title="新建会话" @click="$emit('new-chat')">
      <span class="new-chat-icon" aria-hidden="true">
        <IconNewChat />
      </span>
      <span class="new-chat-text">新建会话</span>
    </button>

    <button class="nav-item" type="button" @click="$emit('go-kb')">
      <IconFolder />
      <span>知识库</span>
    </button>

    <button
      v-if="variant === 'history'"
      class="nav-item active"
      type="button"
      aria-current="page"
    >
      <IconClock />
      <span>历史</span>
    </button>

    <div class="sidebar-section">
      <div class="sidebar-section-header">
        <span class="sidebar-section-title">对话历史</span>
        <button
          v-if="variant === 'home'"
          class="btn-icon"
          type="button"
          title="搜索"
          @click="$emit('toggle-search')"
        >
          <IconSearch />
        </button>
        <button
          v-else
          class="btn-icon"
          type="button"
          title="刷新"
          @click="$emit('refresh')"
        >
          ↻
        </button>
      </div>

      <div v-if="showSearch" class="search-box">
        <input
          ref="searchInputRef"
          class="search-input"
          :placeholder="searchPlaceholder"
          :value="searchText"
          @input="onSearchInput"
        />
      </div>

      <div class="history-list">
        <div
          v-for="item in conversations"
          :key="item.id"
          class="history-item"
          :class="{ active: item.id === activeConversationId }"
          @click="$emit('select', item)"
        >
          <div v-if="variant === 'history'" class="history-time-col">
            {{ formatClock(item.updated_at) }}
          </div>
          <div :class="variant === 'history' ? 'history-content-col' : 'history-title-col'">
            <div class="history-question">{{ item.title || '新对话' }}</div>
            <div v-if="variant === 'history'" class="history-subtext">
              个人 · {{ formatTime(item.updated_at) }}
            </div>
          </div>
          <button
            class="history-delete-btn"
            type="button"
            title="删除"
            @click.stop="$emit('delete', item)"
          >
            <IconTrash />
          </button>
        </div>
        <div v-if="conversations.length === 0" class="history-empty">暂无历史会话</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import IconClock from '../icons/IconClock.vue'
import IconFolder from '../icons/IconFolder.vue'
import IconNewChat from '../icons/IconNewChat.vue'
import IconSearch from '../icons/IconSearch.vue'
import IconTrash from '../icons/IconTrash.vue'
import type { ConversationItem } from '../../types/conversation'

const props = withDefaults(
  defineProps<{
    variant?: 'home' | 'history'
    collapsed?: boolean
    conversations: ConversationItem[]
    activeConversationId?: string | null
    searchText?: string
    showSearch?: boolean
    searchPlaceholder?: string
  }>(),
  {
    variant: 'home',
    collapsed: false,
    activeConversationId: null,
    searchText: '',
    showSearch: true,
    searchPlaceholder: '搜索对话历史...',
  },
)

const emit = defineEmits<{
  'new-chat': []
  select: [item: ConversationItem]
  delete: [item: ConversationItem]
  refresh: []
  'toggle-search': []
  'go-kb': []
  'update:searchText': [value: string]
}>()

const searchInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.showSearch,
  async (visible) => {
    if (visible && props.variant === 'home') {
      await nextTick()
      searchInputRef.value?.focus()
    }
  },
)

const onSearchInput = (event: Event) => {
  emit('update:searchText', (event.target as HTMLInputElement).value)
}

const formatTime = (dateStr: string) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatClock = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.sidebar-left {
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  gap: 8px;
  transition: width 0.3s ease;
  min-height: 0;
}

.sidebar-left.variant-home {
  width: 64px;
}

.sidebar-left.variant-home:not(.collapsed) {
  width: 260px;
  align-items: stretch;
  padding: 12px 10px;
}

.sidebar-left.variant-history {
  width: 280px;
  align-items: stretch;
  padding: 12px 10px;
}

.sidebar-left.collapsed {
  width: 0 !important;
  overflow: hidden;
  padding: 0;
  border-right: none;
}

.new-chat-btn {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  background: #fff;
  color: #333;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.variant-history .new-chat-btn {
  width: 100%;
  height: 44px;
  color: #6b7280;
}

.sidebar-left:not(.collapsed) .new-chat-btn {
  width: 100%;
  flex-direction: row;
  justify-content: flex-start;
  padding: 0 12px;
}

.new-chat-btn:hover {
  background: #f7f7f7;
}

.new-chat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.new-chat-text {
  display: none;
  font-size: 13px;
  white-space: nowrap;
}

.sidebar-left:not(.collapsed) .new-chat-text {
  display: inline;
}

.nav-item {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  color: #666;
  font-size: 12px;
  background: transparent;
  border: none;
}

.variant-history .nav-item {
  width: 100%;
  height: 40px;
  flex-direction: row;
  justify-content: flex-start;
  gap: 8px;
  padding: 0 10px;
  font-size: 13px;
  color: #6b7280;
}

.sidebar-left:not(.collapsed) .nav-item {
  width: 100%;
  flex-direction: row;
  justify-content: flex-start;
  padding: 0 12px;
}

.sidebar-left:not(.collapsed) .nav-item span {
  display: inline;
}

.sidebar-left:not(.collapsed) .nav-item svg {
  margin-right: 8px;
}

.nav-item:hover {
  background: #f5f5f5;
}

.nav-item.active {
  color: var(--dp-primary);
  background: var(--dp-primary-bg);
}

.nav-item svg {
  width: 20px;
  height: 20px;
}

.variant-history .nav-item svg {
  width: 18px;
  height: 18px;
}

.sidebar-section {
  margin-top: 8px;
  border-top: 1px solid #f0f0f0;
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.variant-history .sidebar-section {
  margin-top: 4px;
}

.sidebar-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 8px;
}

.variant-history .sidebar-section-header {
  padding: 0 6px 8px;
}

.sidebar-section-title {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
}

.btn-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #6b7280;
  font-size: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: #f5f5f5;
}

.search-box {
  padding: 0 10px 10px;
}

.variant-history .search-box {
  padding: 0 6px 10px;
}

.search-input {
  width: 100%;
  height: 34px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 0 10px;
  font-size: 13px;
  outline: none;
  color: #6b7280;
  background: #fff;
}

.variant-history .search-input {
  height: 36px;
  border-radius: 6px;
  padding: 0 12px;
}

.search-input:focus {
  border-color: var(--dp-primary);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 8px;
}

.variant-history .history-list {
  padding: 0 6px 8px;
}

.history-item {
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.variant-history .history-item {
  align-items: flex-start;
  padding: 12px;
  gap: 12px;
}

.history-item:hover {
  background: #f5f5f5;
}

.history-item.active {
  background: var(--dp-primary-bg);
}

.history-title-col,
.history-content-col {
  flex: 1;
  min-width: 0;
}

.history-time-col {
  font-size: 12px;
  color: #94a3b8;
  min-width: 40px;
}

.history-question {
  font-size: 13px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.variant-history .history-question {
  font-size: 14px;
}

.history-subtext {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.history-delete-btn {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  flex: 0 0 auto;
}

.history-item:hover .history-delete-btn {
  opacity: 1;
}

.history-delete-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #f56c6c;
}

.history-empty {
  padding: 10px;
  font-size: 12px;
  color: #94a3b8;
}

.variant-history .history-empty {
  padding: 14px 6px;
}
</style>
