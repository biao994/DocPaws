<template>
  <div class="mascot" :style="wrapStyle" aria-hidden="true">
    <img class="mascot-img" :src="emptySvg" alt="" />
  </div>
</template>

<script setup lang="ts">
import emptySvg from '../assets/消息空荡荡的.svg'

const props = withDefaults(
  defineProps<{
    size?: number
  }>(),
  { size: 72 },
)

const wrapStyle = {
  width: `${props.size}px`,
  height: `${props.size}px`,
}
</script>

<style scoped>
.mascot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.mascot-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transform-origin: 50% 60%;
  animation: floaty 2.2s ease-in-out infinite;
}

@keyframes floaty {
  0%,
  100% {
    transform: translateY(0) scale(1);
  }
  50% {
    transform: translateY(-4px) scale(1.06);
  }
}

@media (prefers-reduced-motion: reduce) {
  .mascot-img {
    animation: none !important;
  }
}
</style>

