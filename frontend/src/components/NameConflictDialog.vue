<template>
  <div class="name-conflict-mask" @click.self="emit('cancel')">
    <div class="name-conflict-dialog">
      <div class="name-conflict-title">
        <span class="name-conflict-icon">!</span>
        同名冲突
      </div>
      <p class="name-conflict-desc">
        {{
          conflictScope === 'folder'
            ? '检测到当前位置存在同名文件夹，请选择操作'
            : '检测到当前位置存在同名项，请选择操作'
        }}
      </p>
      <div class="name-conflict-filename">{{ fileName }}</div>
      <div class="name-conflict-actions">
        <button type="button" class="name-conflict-btn secondary" @click="emit('keepAll')">保留全部</button>
        <button v-if="allowReplace" type="button" class="name-conflict-btn primary" @click="emit('replace')">
          替换
        </button>
        <button type="button" class="name-conflict-btn secondary" @click="emit('cancel')">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  fileName: string
  allowReplace: boolean
  conflictScope?: 'file' | 'folder'
}>()

const emit = defineEmits<{
  cancel: []
  replace: []
  keepAll: []
}>()
</script>

<style scoped>
.name-conflict-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4000;
}

.name-conflict-dialog {
  width: min(420px, 92vw);
  background: #fff;
  border-radius: 10px;
  padding: 20px 22px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}

.name-conflict-title {
  font-size: 16px;
  font-weight: 600;
  color: #222;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.name-conflict-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #e85d4c;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.name-conflict-desc {
  font-size: 13px;
  color: #666;
  margin: 0 0 12px;
  line-height: 1.5;
}

.name-conflict-filename {
  font-size: 13px;
  color: #333;
  padding: 10px 12px;
  background: #f7f7f7;
  border-radius: 6px;
  margin-bottom: 18px;
  word-break: break-all;
}

.name-conflict-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.name-conflict-btn {
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
}

.name-conflict-btn.secondary {
  background: #f0f0f0;
  color: #333;
}

.name-conflict-btn.secondary:hover {
  background: #e4e4e4;
}

.name-conflict-btn.primary {
  background: #2563eb;
  color: #fff;
}

.name-conflict-btn.primary:hover {
  background: #1d4ed8;
}
</style>
