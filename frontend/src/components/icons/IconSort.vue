<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="strokeWidth">
    <path d="M6 4l-3 3h6l-3-3z" />
    <path d="M6 20l3-3H3l3 3z" />
    <line x1="12" y1="7" x2="21" y2="7" />
    <line x1="12" y1="17" x2="21" y2="17" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number; strokeWidth?: number | string }>(), { size: 16, strokeWidth: 2 })
</script>
