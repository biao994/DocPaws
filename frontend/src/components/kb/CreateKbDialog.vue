<template>
  <div v-if="open" class="create-kb-mask" @click.self="$emit('close')">
    <div class="create-kb-dialog">
      <div class="create-kb-title">新建个人知识库</div>
      <p class="create-kb-desc">将创建归属于当前账号的知识库，可随后上传文档并与 AI 对话。</p>
      <input
        :value="name"
        class="create-kb-input"
        type="text"
        placeholder="知识库名称，例如「项目资料」"
        maxlength="120"
        :disabled="submitting"
        @input="onInput"
        @keyup.enter="$emit('submit')"
      />
      <p v-if="error" class="create-kb-error">{{ error }}</p>
      <div class="create-kb-actions">
        <button type="button" class="create-kb-btn secondary" :disabled="submitting" @click="$emit('close')">
          取消
        </button>
        <button type="button" class="create-kb-btn primary" :disabled="submitting" @click="$emit('submit')">
          {{ submitting ? '创建中…' : '创建' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  open: boolean
  name: string
  error?: string
  submitting?: boolean
}>()

const emit = defineEmits<{
  close: []
  submit: []
  'update:name': [value: string]
}>()

const onInput = (event: Event) => {
  emit('update:name', (event.target as HTMLInputElement).value)
}
</script>

<style scoped>
.create-kb-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4000;
}

.create-kb-dialog {
  width: min(420px, 92vw);
  background: #fff;
  border-radius: 10px;
  padding: 20px 22px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}

.create-kb-title {
  font-size: 16px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 8px;
}

.create-kb-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 0 0 14px;
  line-height: 1.5;
}

.create-kb-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}

.create-kb-input:focus {
  border-color: var(--dp-primary);
}

.create-kb-error {
  margin: 10px 0 0;
  font-size: 13px;
  color: #c53030;
}

.create-kb-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.create-kb-btn {
  min-width: 88px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  border: none;
}

.create-kb-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.create-kb-btn.secondary {
  background: #f5f5f5;
  color: #6b7280;
}

.create-kb-btn.primary {
  background: var(--dp-primary);
  color: #fff;
}
</style>
