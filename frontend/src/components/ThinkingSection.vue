<template>
  <div v-if="text" class="thinking-block">
    <button type="button" class="thinking-toggle" @click="open = !open">
      <span class="thinking-chevron">{{ open ? '▼' : '▶' }}</span>
      思考过程
    </button>
    <pre v-show="open" class="thinking-body">{{ text }}</pre>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  text?: string
}>()

const open = ref(true)
</script>

<style scoped>
.thinking-block {
  margin-bottom: 8px;
}

.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: none;
  background: transparent;
  font-size: 12px;
  color: #8c8c8c;
  cursor: pointer;
}

.thinking-chevron {
  font-size: 10px;
}

.thinking-body {
  margin: 8px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.55;
  color: #595959;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}
</style>
