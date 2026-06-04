<template>
  <div class="home-content">
    <div class="home-logo">
      <MascotLogo />
    </div>
    <div class="home-title">DocPaws</div>
    <div class="home-subtitle">猫爪轻轻一拍，就给你答案</div>
    <div class="ai-input-bar">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import MascotLogo from '../MascotLogo.vue'
</script>

<style scoped>
.home-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  padding: 40px;
  min-height: 0;
}

.home-logo {
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.home-title {
  font-size: 32px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 8px;
  letter-spacing: 0.2px;
  line-height: 1.1;
  animation: dp-title-float 3.2s ease-in-out infinite;
  will-change: transform, filter;
  filter: drop-shadow(0 10px 22px rgba(0, 0, 0, 0.08));
}

.home-subtitle {
  font-size: 16px;
  color: #999;
  margin-bottom: 40px;
  animation: dp-subtitle-in 720ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
  opacity: 0.98;
}

.home-subtitle::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -10px;
  width: min(240px, 82%);
  height: 2px;
  transform: translateX(-50%);
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(17, 24, 39, 0), rgba(17, 24, 39, 0.65), rgba(17, 24, 39, 0));
  opacity: 0.9;
  animation: dp-underline 2.8s ease-in-out infinite;
}

.home-subtitle {
  position: relative;
}

@keyframes dp-title-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}

@keyframes dp-subtitle-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes dp-underline {
  0%,
  100% {
    opacity: 0.55;
    transform: translateX(-50%) scaleX(0.92);
  }
  50% {
    opacity: 1;
    transform: translateX(-50%) scaleX(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-title,
  .home-subtitle,
  .home-subtitle::after {
    animation: none !important;
  }
}

.ai-input-bar {
  width: 100%;
  padding: 20px 0;
  border-top: none;
  background: transparent;
  display: flex;
  justify-content: center;
  margin-top: 40px;
}
</style>
