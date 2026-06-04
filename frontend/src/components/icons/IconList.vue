<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="strokeWidth">
    <line x1="4" y1="6" x2="20" y2="6" />
    <line x1="4" y1="12" x2="20" y2="12" />
    <line x1="4" y1="18" x2="20" y2="18" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number; strokeWidth?: number | string }>(), { size: 16, strokeWidth: 2 })
</script>
