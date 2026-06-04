<template>
  <div class="page-root">
    <div class="top-nav">
      <div class="nav-left">
        <slot name="nav-left">
          <button class="btn-collapse" type="button" title="收起侧边栏" @click="$emit('toggle-sidebar')">
            <IconChevronLeft />
          </button>
        </slot>
      </div>
      <ChatUserMenu />
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
import ChatUserMenu from './ChatUserMenu.vue'
import IconChevronLeft from './icons/IconChevronLeft.vue'

defineEmits<{ 'toggle-sidebar': [] }>()
</script>

<style scoped>
.page-root {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.top-nav {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  flex-shrink: 0;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-collapse {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #333;
}

.btn-collapse:hover {
  background: #f5f5f5;
}
</style>
