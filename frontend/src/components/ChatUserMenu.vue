<template>
  <div class="nav-actions" style="position: relative">
    <div ref="userInfoEl" class="user-info" @click.stop="toggleSettings">
      <div class="user-avatar">{{ avatarLetter }}</div>
      <span class="user-name">{{ userDisplayName }}</span>
      <IconChevronDown />
    </div>
    <div ref="settingsMenuEl" class="settings-menu" :class="{ show: showSettings }">
      <div class="settings-item logout" @click.stop="handleLogout">退出登录</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { logout as authLogout } from '../api/auth'
import { clearSession, currentUser } from '../auth/session'
import IconChevronDown from './icons/IconChevronDown.vue'

const showSettings = ref(false)
const userInfoEl = ref<HTMLElement | null>(null)
const settingsMenuEl = ref<HTMLElement | null>(null)

const userDisplayName = computed(
  () => currentUser.value?.username || currentUser.value?.email || '用户',
)
const avatarLetter = computed(() => {
  const n = userDisplayName.value.trim()
  return n ? n.charAt(0).toUpperCase() : 'U'
})

const toggleSettings = () => {
  showSettings.value = !showSettings.value
}

const handleLogout = async () => {
  showSettings.value = false
  try {
    await authLogout()
  } catch {
    /* noop */
  }
  clearSession()
}

const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as Node
  if (userInfoEl.value?.contains(target) || settingsMenuEl.value?.contains(target)) return
  showSettings.value = false
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.nav-actions {
  position: relative;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.user-info:hover {
  background: #f5f5f5;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--dp-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.user-name {
  font-size: 14px;
  color: #333;
}

.settings-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  min-width: 160px;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-8px);
  transition: all 0.2s;
  z-index: 1000;
}

.settings-menu.show {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.settings-item {
  padding: 12px 16px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  transition: background 0.2s;
}

.settings-item:hover {
  background: #f5f5f5;
}

.settings-item.logout {
  color: #ff4d4f;
}
</style>
