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
      <AttachmentChip :name="attachmentName" @remove="emit('clearAttachment')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import AttachmentChip from './AttachmentChip.vue'
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
</style>
