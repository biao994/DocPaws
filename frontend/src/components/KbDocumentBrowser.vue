<template>
  <div class="file-grid">
    <div v-if="items.length === 0" class="empty-docs">{{ emptyMessage }}</div>
    <div v-else-if="viewMode === 'grid'" class="grid-container">
      <div
        v-for="item in items"
        :key="item.id"
        class="file-card"
        :class="{ active: isFileActive(item) }"
        @click="emit('openCard', item)"
      >
        <div class="file-card-actions">
          <div class="more-menu-wrap">
            <button
              class="more-btn"
              type="button"
              title="更多"
              @click.stop="toggleMenu(item.id)"
            >
              ···
            </button>
            <div v-if="openMenuId === item.id" class="more-menu" @click.stop>
              <button type="button" class="more-item" @click="handleAction('rename', item)">重命名</button>
              <button type="button" class="more-item danger" @click="handleAction('delete', item)">删除</button>
              <div v-if="item.kind === 'file'" class="more-divider"></div>
              <button
                v-if="item.kind === 'file'"
                type="button"
                class="more-item"
                @click="handleAction('download', item)"
              >
                下载
              </button>
            </div>
          </div>
        </div>
        <div class="file-icon" :class="[item.type, { 'pdf-preview': item.kind === 'file' && !!item.docId }]">
          <iframe
            v-if="item.kind === 'file' && item.docId"
            class="pdf-card-preview-frame"
            :src="getPdfCardSrc(item.docId)"
            title="PDF预览"
            scrolling="no"
          ></iframe>
          <svg v-else-if="item.kind === 'folder'" width="29" height="29" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <svg v-else width="29" height="29" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <div class="file-name">{{ item.name }}</div>
        <div class="file-meta">
          <template v-if="item.kind === 'folder'">
            <span>{{ item.size }}</span>
            <span>·</span>
            <span>{{ item.updatedAt }}</span>
          </template>
          <template v-else>
            <span class="file-tag" :class="item.type">{{ item.typeLabel }}</span>
            <span>{{ item.updatedAt }}</span>
          </template>
        </div>
      </div>
    </div>
    <div v-else class="list-container">
      <div
        v-for="item in items"
        :key="`list-${item.id}`"
        class="list-row"
        :class="{ active: isFileActive(item) }"
        @click="emit('openCard', item)"
      >
        <div class="list-name">
          <svg v-if="item.kind === 'folder'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="display: inline; vertical-align: middle; margin-right: 6px">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="display: inline; vertical-align: middle; margin-right: 6px">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          {{ item.name }}
        </div>
        <div class="list-meta">
          <span v-if="item.kind === 'folder'">{{ item.size }}</span>
          <span v-else class="file-tag" :class="item.type">{{ item.typeLabel }}</span>
          <span>{{ item.updatedAt }}</span>
          <div class="list-actions">
            <div class="more-menu-wrap">
              <button class="more-btn" type="button" title="更多" @click.stop="toggleMenu(item.id)">···</button>
              <div v-if="openMenuId === item.id" class="more-menu" @click.stop>
                <button type="button" class="more-item" @click="handleAction('rename', item)">重命名</button>
                <button type="button" class="more-item danger" @click="handleAction('delete', item)">删除</button>
                <div v-if="item.kind === 'file'" class="more-divider"></div>
                <button
                  v-if="item.kind === 'file'"
                  type="button"
                  class="more-item"
                  @click="handleAction('download', item)"
                >
                  下载
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import type { KbBrowseCard } from '../types/kbBrowseCard'

export type { KbBrowseCard }

const props = defineProps<{
  viewMode: 'grid' | 'list'
  items: readonly KbBrowseCard[]
  emptyMessage: string
  /** 当前是否为「按单文件问答」范围 */
  fileScopeActive: boolean
  selectedDocId: string | null
  getPdfCardSrc: (docId?: string) => string
}>()

const emit = defineEmits<{
  openCard: [item: KbBrowseCard]
  renameItem: [item: KbBrowseCard]
  deleteItem: [item: KbBrowseCard]
  downloadDoc: [docId: string]
}>()

const openMenuId = ref<string | null>(null)

function isFileActive(item: KbBrowseCard) {
  return item.kind === 'file' && props.fileScopeActive && props.selectedDocId != null && item.docId === props.selectedDocId
}

function toggleMenu(id: string) {
  openMenuId.value = openMenuId.value === id ? null : id
}

function handleAction(action: 'rename' | 'delete' | 'download', item: KbBrowseCard) {
  openMenuId.value = null
  if (action === 'rename') return emit('renameItem', item)
  if (action === 'delete') return emit('deleteItem', item)
  if (action === 'download' && item.kind === 'file' && item.docId) return emit('downloadDoc', item.docId)
}

function handleClickOutside(e: MouseEvent) {
  const t = e.target as HTMLElement | null
  if (!t) return
  if (!t.closest('.more-menu-wrap')) {
    openMenuId.value = null
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
.file-grid {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.grid-container {
  display: grid;
  /* 相对最初尺寸 90%：列 180px、间距 14px（原 200 / 16） */
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
}

.list-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.list-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
}

.list-row.active {
  border-color: var(--dp-primary);
  background: #f6fffa;
}

.list-name {
  font-size: 14px;
  color: #6b7280;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.list-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #94a3b8;
}

.list-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.file-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 5px;
  margin-bottom: 5px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.more-menu-wrap {
  position: relative;
}

.more-btn {
  border: none;
  background: #f5f5f5;
  color: #6b7280;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
}

.more-btn:hover {
  background: #ededed;
}

.more-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  min-width: 120px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.14);
  padding: 6px;
  z-index: 80;
}

.more-item {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 9px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
}

.more-item:hover {
  background: #f5f5f5;
}

.more-item.danger {
  color: var(--dp-danger-text, #6b7280);
}

.more-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 4px 6px;
}

.empty-docs {
  color: #94a3b8;
  font-size: 13px;
  padding: 20px 0;
  text-align: center;
}

.file-card {
  background: #fff;
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.file-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border-color: #e8e8e8;
}

.file-card.active {
  border-color: var(--dp-primary);
  background: #f6fffa;
}

.grid-container .file-card:hover .file-card-actions,
.grid-container .file-card.active .file-card-actions {
  opacity: 1;
  pointer-events: auto;
}

.list-row:hover .list-actions,
.list-row.active .list-actions {
  opacity: 1;
  pointer-events: auto;
}

.file-icon {
  width: 100%;
  height: 108px;
  background: #f5f5f5;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 11px;
  font-size: 43px;
  position: relative;
  overflow: hidden;
}

.file-icon.folder {
  background: var(--dp-primary-bg);
  color: var(--dp-primary);
}

.file-icon.pdf {
  background: #fff2f0;
  color: #ff4d4f;
}

.file-icon.pdf-preview {
  background: #f6f8fb;
  color: transparent;
}

.pdf-card-preview-frame {
  width: 170%;
  height: 185%;
  border: 0;
  pointer-events: none;
  overflow: hidden;
  scrollbar-width: none;
  position: absolute;
  top: 0;
  left: 50%;
  transform: translate(-50%, -34%);
  transform-origin: top center;
}

.file-icon.pdf-preview::before,
.file-icon.pdf-preview::after {
  content: '';
  position: absolute;
  z-index: 2;
  background: #f6f8fb;
  pointer-events: none;
}

.file-icon.pdf-preview::before {
  top: 0;
  right: 0;
  width: 11px;
  height: 100%;
}

.file-icon.pdf-preview::after {
  left: 0;
  bottom: 0;
  width: 100%;
  height: 11px;
}

.file-icon.word {
  background: #e6f4ff;
  color: #1890ff;
}

.file-name {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 7px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-meta {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: #94a3b8;
}

.file-tag {
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.file-tag.pdf {
  background: #fff2f0;
  color: #ff4d4f;
}

.file-tag.word {
  background: #e6f4ff;
  color: #1890ff;
}

.file-tag.folder {
  background: var(--dp-primary-bg);
  color: var(--dp-primary);
}
</style>
