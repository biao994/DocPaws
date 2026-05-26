<template>
  <div class="ai-input-bar">
    <div class="composer-wrap">
      <ComposerBox
        v-model="question"
        shell-variant="card"
        :enable-kb-picker="false"
        :disabled-send="!hasKb || !question.trim()"
        :show-error-banner="false"
        :placeholder="placeholder"
        @focus="emit('focus')"
        @send="emit('send')"
        @attachment="emit('attachment')"
      />
      <div v-if="attachmentName" class="attachment-chip">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="display: inline; vertical-align: middle; margin-right: 4px">
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
        </svg>
        {{ attachmentName }}
        <button type="button" class="attachment-remove" @click="emit('clearAttachment')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ComposerBox from './ComposerBox.vue'

const question = defineModel<string>({ required: true })

defineProps<{
  hasKb: boolean
  attachmentName?: string
  placeholder: string
}>()

const emit = defineEmits<{
  focus: []
  send: []
  attachment: []
  clearAttachment: []
}>()
</script>

<style scoped>
.ai-input-bar {
  width: 100%;
  padding: 20px 0;
  border-top: none;
  background: transparent;
  display: flex;
  justify-content: center;
  position: relative;
}

.composer-wrap {
  position: relative;
  width: min(720px, 92%);
}

.attachment-chip {
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
}

.attachment-remove {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
}
</style>
