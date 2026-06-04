<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <g v-if="expanded">
      <line x1="20" y1="4" x2="14" y2="10" />
      <polyline points="16 10 14 10 14 8" />
      <line x1="4" y1="20" x2="10" y2="14" />
      <polyline points="8 14 10 14 10 16" />
    </g>
    <g v-else>
      <path d="M8 3H5a2 2 0 0 0-2 2v3" />
      <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
      <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
      <path d="M3 16v3a2 2 0 0 0 2 2h3" />
    </g>
  </svg>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{ size?: number; strokeWidth?: number | string; expanded?: boolean }>(),
  { size: 14, strokeWidth: 1.6, expanded: false },
)
</script>
