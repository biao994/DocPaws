<template>
  <div class="chat-thinking-placeholder" role="status" aria-live="polite">
    <span class="chat-thinking-placeholder-text">{{ text }}</span>
    <div class="chat-thinking-placeholder-bar" aria-hidden="true" />
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    text?: string
  }>(),
  {
    text: '正在思考中...',
  },
)
</script>

<style scoped>
.chat-thinking-placeholder {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
  min-width: 120px;
}

.chat-thinking-placeholder-text {
  font-size: 14px;
  line-height: 1.5;
  color: #9ca3af;
}

.chat-thinking-placeholder-bar {
  width: 72px;
  height: 4px;
  border-radius: 999px;
  background: linear-gradient(90deg, #e5e7eb 0%, #d1d5db 50%, #e5e7eb 100%);
  background-size: 200% 100%;
  animation: chat-thinking-shimmer 1.2s ease-in-out infinite;
}

@keyframes chat-thinking-shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>
