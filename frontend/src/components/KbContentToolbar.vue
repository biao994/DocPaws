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
        <IconSearch :size="16" class="search-icon" />
        <input class="search-input-main" v-model="searchQuery" placeholder="在知识库中搜索" />
        <button class="search-clear-x" type="button" title="收起搜索" @click="emit('toggleSearch')">
          <IconClose :size="14" />
        </button>
      </div>
      <button v-else type="button" class="toolbar-btn" title="搜索" @click="emit('toggleSearch')">
        <IconSearch :size="16" />
      </button>
      <button type="button" class="toolbar-btn" title="视图切换" @click="emit('toggleViewMode')">
        <IconGrid v-if="viewMode === 'grid'" :size="16" />
        <IconList v-else :size="16" />
      </button>
      <button type="button" class="toolbar-btn" :title="`排序：${sortLabel}`" @click="emit('toggleSortMode')">
        <IconSort :size="16" />
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
          <IconPlus :size="16" />
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
import IconClose from './icons/IconClose.vue'
import IconGrid from './icons/IconGrid.vue'
import IconList from './icons/IconList.vue'
import IconPlus from './icons/IconPlus.vue'
import IconSearch from './icons/IconSearch.vue'
import IconSort from './icons/IconSort.vue'
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

.search-pill {
  display: flex;
  align-items: center;
  gap: 8px;
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
