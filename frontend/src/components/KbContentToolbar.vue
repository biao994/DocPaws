<template>
  <div class="content-header">
    <div class="content-title-row">
      <KbPathBreadcrumb
        :crumbs="pathCrumbs"
        :can-go-back="canGoBack"
        :can-go-forward="canGoForward"
        @back="emit('pathBack')"
        @forward="emit('pathForward')"
        @navigate="emit('pathNavigate', $event)"
      />
    </div>
    <div class="content-actions">
      <div v-if="showSearch" class="search-pill">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="6"></circle>
          <line x1="16" y1="16" x2="21" y2="21"></line>
        </svg>
        <input class="search-input-main" v-model="searchQuery" placeholder="在知识库中搜索" />
        <button class="search-clear-x" type="button" title="收起搜索" @click="emit('toggleSearch')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <button v-else type="button" class="toolbar-btn" title="搜索" @click="emit('toggleSearch')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="6"></circle>
          <line x1="16" y1="16" x2="21" y2="21"></line>
        </svg>
      </button>
      <button type="button" class="toolbar-btn" title="视图切换" @click="emit('toggleViewMode')">
        <svg v-if="viewMode === 'grid'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="7" height="7"></rect>
          <rect x="14" y="3" width="7" height="7"></rect>
          <rect x="14" y="14" width="7" height="7"></rect>
          <rect x="3" y="14" width="7" height="7"></rect>
        </svg>
        <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="4" y1="6" x2="20" y2="6"></line>
          <line x1="4" y1="12" x2="20" y2="12"></line>
          <line x1="4" y1="18" x2="20" y2="18"></line>
        </svg>
      </button>
      <button type="button" class="toolbar-btn" :title="`排序：${sortLabel}`" @click="emit('toggleSortMode')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 4l-3 3h6l-3-3z"></path>
          <path d="M6 20l3-3H3l3 3z"></path>
          <line x1="12" y1="7" x2="21" y2="7"></line>
          <line x1="12" y1="17" x2="21" y2="17"></line>
        </svg>
      </button>
      <div class="upload-menu-wrap">
        <button
          type="button"
          class="toolbar-btn"
          :class="{ 'toolbar-btn--disabled': !uploadEnabled }"
          :disabled="!uploadEnabled"
          :title="uploadEnabled ? '上传/新建' : '请先选择知识库'"
          @click="uploadEnabled && emit('toggleUploadMenu')"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14"></path>
            <path d="M5 12h14"></path>
          </svg>
        </button>
        <div v-if="showUploadMenu" class="upload-menu">
          <button type="button" class="upload-menu-item" @click="emit('openFile')">本地文件</button>
          <button type="button" class="upload-menu-item" @click="emit('openFolder')">本地文件夹</button>
          <button type="button" class="upload-menu-item" @click="emit('createFolder')">新增文件夹</button>
        </div>

        <UploadProgressPanel
          v-if="showUploadProgressPanel"
          :tasks="uploadTasks"
          @close-finished="emit('closeUploadProgressPanel')"
          @open-file="emit('openFile')"
          @open-folder="emit('openFolder')"
          @create-folder="emit('createFolder')"
          @cancel-task="emit('cancelUploadTask', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import UploadProgressPanel from './UploadProgressPanel.vue'
import KbPathBreadcrumb from './KbPathBreadcrumb.vue'
import type { PathCrumb } from '../composables/useKbPathNavigation'

export type ToolbarUploadTask = {
  id: string
  fileName: string
  uploadProgress: number
  indexProgress: number
  status: 'uploading' | 'indexing' | 'succeeded' | 'failed'
  errorMessage?: string
}

const searchQuery = defineModel<string>('searchQuery', { default: '' })

withDefaults(
  defineProps<{
    pathCrumbs: readonly PathCrumb[]
    canGoBack: boolean
    canGoForward: boolean
    showSearch: boolean
    viewMode: 'grid' | 'list'
    sortLabel: string
    showUploadMenu: boolean
    uploadTasks: ToolbarUploadTask[]
    showUploadProgressPanel: boolean
    uploadEnabled?: boolean
  }>(),
  { uploadEnabled: true },
)

const emit = defineEmits<{
  pathBack: []
  pathForward: []
  pathNavigate: [crumb: PathCrumb]
  toggleSearch: []
  toggleViewMode: []
  toggleSortMode: []
  toggleUploadMenu: []
  openFile: []
  openFolder: []
  createFolder: []
  closeUploadProgressPanel: []
  cancelUploadTask: [taskId: string]
}>()
</script>

<style scoped>
.content-header {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.content-title-row {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.content-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: #f5f5f5;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.toolbar-btn:hover {
  background: var(--dp-primary-bg);
  color: var(--dp-primary);
}

.toolbar-btn--disabled,
.toolbar-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.toolbar-btn--disabled:hover,
.toolbar-btn:disabled:hover {
  background: #f5f5f5;
  color: #6b7280;
}

.upload-menu-wrap {
  position: relative;
}

.upload-menu {
  position: absolute;
  top: 36px;
  right: 0;
  width: 130px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.16);
  padding: 6px;
  z-index: 60;
}

.upload-menu-item {
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

.upload-menu-item:hover {
  background: #f5f5f5;
}

.upload-menu-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 4px 6px;
}

.search-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  /* 原来偏长：缩到约 1/3 */
  width: min(320px, 14vw);
  padding: 6px 10px;
  border: 1px solid #e8e8e8;
  border-radius: 999px;
  background: #fff;
}

.search-icon {
  color: #94a3b8;
  flex: 0 0 auto;
}

.search-input-main {
  flex: 1;
  border: none;
  outline: none;
  padding: 6px 0;
  font-size: 13px;
  background: transparent;
}

.search-clear-x {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid #e8e8e8;
  background: #fff;
  color: #94a3b8;
  padding: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.search-clear-x:hover {
  background: #f5f5f5;
  color: #6b7280;
}
</style>
