<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="strokeWidth">
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number | string; strokeWidth?: number | string }>(), { size: 16, strokeWidth: 2 })
</script>
