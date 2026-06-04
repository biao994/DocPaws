<template>
  <div v-if="name" class="attachment-chip">
    <IconPaperclip :size="14" class="attachment-icon" />
    {{ name }}
    <button type="button" class="attachment-remove" title="移除附件" @click="$emit('remove')">
      <IconClose :size="12" />
    </button>
  </div>
</template>

<script setup lang="ts">
import IconClose from './icons/IconClose.vue'
import IconPaperclip from './icons/IconPaperclip.vue'

defineProps<{ name?: string }>()
defineEmits<{ remove: [] }>()
</script>

<style scoped>
.attachment-chip {
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
}

.attachment-icon {
  flex-shrink: 0;
}

.attachment-remove {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  padding: 0;
}
</style>
