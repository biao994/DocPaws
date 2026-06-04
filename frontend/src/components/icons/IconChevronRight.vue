<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="strokeWidth">
    <polyline points="9 18 15 12 9 6" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{ size?: number; strokeWidth?: number | string }>(),
  { size: 16, strokeWidth: 2 },
)
</script>
