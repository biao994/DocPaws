<template>
  <div class="kb-path-bar">
    <div class="kb-path-nav">
      <button
        type="button"
        class="path-nav-btn"
        title="后退"
        :disabled="!canGoBack"
        @click="emit('back')"
      >
        <IconChevronLeft :size="16" />
      </button>
      <button
        type="button"
        class="path-nav-btn"
        title="前进"
        :disabled="!canGoForward"
        @click="emit('forward')"
      >
        <IconChevronRight :size="16" />
      </button>
    </div>
    <span class="path-divider" aria-hidden="true"></span>
    <nav class="kb-path-crumbs" aria-label="当前位置">
      <template v-for="(crumb, idx) in crumbs" :key="crumbKey(crumb, idx)">
        <span v-if="idx > 0" class="path-sep" aria-hidden="true">›</span>
        <button
          v-if="idx < crumbs.length - 1"
          type="button"
          class="path-crumb path-crumb--link"
          :title="crumb.label"
          @click="emit('navigate', crumb)"
        >
          {{ crumb.label }}
        </button>
        <span
          v-else
          class="path-crumb path-crumb--current"
          :title="crumb.label"
        >
          {{ crumb.label }}
        </span>
      </template>
    </nav>
  </div>
</template>

<script setup lang="ts">
import IconChevronLeft from './icons/IconChevronLeft.vue'
import IconChevronRight from './icons/IconChevronRight.vue'
import type { PathCrumb } from '../composables/useKbPathNavigation'

defineProps<{
  crumbs: readonly PathCrumb[]
  canGoBack: boolean
  canGoForward: boolean
}>()

const emit = defineEmits<{
  back: []
  forward: []
  navigate: [crumb: PathCrumb]
}>()

function crumbKey(crumb: PathCrumb, idx: number) {
  return `${crumb.folderId ?? 'root'}-${idx}`
}
</script>

<style scoped>
.kb-path-bar {
  --path-row-h: 32px;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
  height: var(--path-row-h);
}

.kb-path-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  height: var(--path-row-h);
}

.path-nav-btn {
  width: var(--path-row-h);
  height: var(--path-row-h);
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

.path-nav-btn:hover:not(:disabled) {
  background: #f5f5f5;
  color: #6b7280;
}

.path-nav-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.path-divider {
  width: 1px;
  height: 16px;
  background: #e8e8e8;
  flex-shrink: 0;
  align-self: center;
}

.kb-path-crumbs {
  display: flex;
  align-items: center;
  gap: 2px;
  min-width: 0;
  flex: 1;
  overflow: hidden;
  height: var(--path-row-h);
}

.path-sep {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: var(--path-row-h);
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
  user-select: none;
}

.path-crumb {
  display: inline-flex;
  align-items: center;
  max-width: 200px;
  height: var(--path-row-h);
  font-size: 14px;
  line-height: 20px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-sizing: border-box;
}

.path-crumb--link {
  border: none;
  background: transparent;
  padding: 0 6px;
  border-radius: 4px;
  color: #94a3b8;
  cursor: pointer;
}

.path-crumb--link:hover {
  background: #f5f5f5;
  color: #6b7280;
}

.path-crumb--current {
  color: #1f2937;
  font-weight: 600;
  padding: 0 6px;
}
</style>
