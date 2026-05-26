<template>
  <div class="upload-progress-panel">
    <div class="upload-progress-header">
      <div class="upload-progress-title">处理进度</div>
      <button class="upload-progress-close-btn" type="button" @click="emit('closeFinished')">关闭</button>
    </div>

    <div class="upload-progress-list">
      <div v-for="t in tasks" :key="t.id" class="upload-progress-item">
        <div class="upload-progress-item-top">
          <div class="upload-progress-filename" :title="t.fileName">
            {{ t.fileName }}
          </div>
          <div class="upload-progress-item-actions">
            <div class="upload-progress-percent">
              {{ overallPercent(t) }}%
            </div>
            <button
              v-if="canCancel(t.status)"
              type="button"
              class="upload-progress-cancel-btn"
              title="取消"
              @click="emit('cancelTask', t.id)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
        </div>

        <div class="upload-progress-bar">
          <div
            class="upload-progress-fill"
            :class="{ 'upload-progress-fill--failed': t.status === 'failed' }"
            :style="{ width: `${overallPercent(t)}%` }"
          />
        </div>

        <div class="upload-progress-status">
          <span :class="{ 'upload-progress-status--error': t.status === 'failed' }">
            {{ statusLabel(t.status) }}
          </span>
          <span
            v-if="t.status === 'failed' && t.errorMessage"
            class="upload-progress-error"
            :title="t.errorMessage"
          >
            {{ t.errorMessage }}
          </span>
        </div>
      </div>
    </div>

    <div class="upload-progress-actions">
      <div class="upload-progress-continue-wrap">
        <button
          class="upload-progress-continue-btn"
          type="button"
          @click="showContinueMenu = !showContinueMenu"
        >
          继续上传
        </button>
        <div v-if="showContinueMenu" class="upload-progress-continue-menu">
          <button type="button" class="upload-progress-continue-item" @click="pickFile">本地文件</button>
          <button type="button" class="upload-progress-continue-item" @click="pickFolder">本地文件夹</button>
          <button type="button" class="upload-progress-continue-item" @click="pickCreateFolder">新增文件夹</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  canCancelUploadTask,
  overallUploadPercent,
  uploadProgressStatusLabel,
} from '../utils/kbUploadProgress'

type UploadProgressTask = {
  id: string
  fileName: string
  uploadProgress: number
  indexProgress: number
  status: 'uploading' | 'indexing' | 'succeeded' | 'failed'
  errorMessage?: string
}

defineProps<{
  tasks: UploadProgressTask[]
}>()

const emit = defineEmits<{
  closeFinished: []
  openFile: []
  openFolder: []
  createFolder: []
  cancelTask: [taskId: string]
}>()

const showContinueMenu = ref(false)

const pickFile = () => {
  showContinueMenu.value = false
  emit('openFile')
}

const pickFolder = () => {
  showContinueMenu.value = false
  emit('openFolder')
}

const pickCreateFolder = () => {
  showContinueMenu.value = false
  emit('createFolder')
}

const canCancel = canCancelUploadTask
const statusLabel = uploadProgressStatusLabel

function overallPercent(t: UploadProgressTask) {
  return overallUploadPercent(t.uploadProgress, t.indexProgress)
}
</script>

<style scoped>
.upload-progress-panel {
  position: absolute;
  top: 52px;
  right: 0;
  width: 360px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.16);
  z-index: 80;
  border: 1px solid #eee;
}

.upload-progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #f3f3f3;
}

.upload-progress-title {
  font-weight: 700;
  font-size: 14px;
  color: #333;
}

.upload-progress-close-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #999;
  font-size: 12px;
}

.upload-progress-close-btn:hover {
  color: #666;
  background: #f5f5f5;
  border-radius: 6px;
}

.upload-progress-list {
  padding: 10px 14px;
  max-height: 320px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.upload-progress-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-progress-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.upload-progress-item-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.upload-progress-filename {
  font-size: 12px;
  color: #333;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-progress-percent {
  font-size: 12px;
  color: #666;
  min-width: 36px;
  text-align: right;
}

.upload-progress-cancel-btn {
  width: 26px;
  height: 26px;
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

.upload-progress-cancel-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #f56c6c;
}

.upload-progress-bar {
  height: 10px;
  background: #f0f0f0;
  border-radius: 999px;
  overflow: hidden;
}

.upload-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #52c41a, var(--dp-primary));
  transition: width 0.25s ease;
}

.upload-progress-fill--failed {
  background: #ffccc7;
}

.upload-progress-status {
  font-size: 12px;
  color: #888;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.upload-progress-status--error {
  color: #d4380d;
  font-weight: 600;
}

.upload-progress-error {
  color: #d4380d;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-progress-actions {
  padding: 10px 14px 14px;
  border-top: 1px solid #f3f3f3;
}

.upload-progress-continue-wrap {
  position: relative;
}

.upload-progress-continue-menu {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 6px);
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.16);
  padding: 6px;
  z-index: 90;
  border: 1px solid #eee;
}

.upload-progress-continue-item {
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

.upload-progress-continue-item:hover {
  background: #f5f5f5;
}

.upload-progress-continue-btn {
  width: 100%;
  border: none;
  background: #f5f5f5;
  color: #555;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  font-weight: 600;
}

.upload-progress-continue-btn:hover {
  background: var(--dp-primary-bg);
  color: var(--dp-primary);
}
</style>
