<template>
  <div class="top-nav">
    <div class="nav-left">
      <button type="button" class="top-back-btn" title="返回" @click="emit('navigateHome')">
        <MascotLogo :size="28" />
      </button>
    </div>
    <div class="nav-actions">
      <div class="user-info" @click.stop="emit('toggleSettings')">
        <div class="user-avatar">{{ avatarLetter }}</div>
        <span class="user-name">{{ props.displayName || '用户' }}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </div>
      <div class="settings-menu" :class="{ show: settingsOpen }">
        <!-- 暂隐藏：反馈入口未接后端 -->
        <template v-if="false">
          <div class="settings-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path
                d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
              ></path>
            </svg>
            提交反馈
          </div>
          <div class="settings-divider"></div>
        </template>
        <div class="settings-item logout" @click.stop="emit('logout')">退出登录</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MascotLogo from './MascotLogo.vue'

const props = defineProps<{
  settingsOpen: boolean
  displayName?: string
}>()

const emit = defineEmits<{
  navigateHome: []
  toggleSettings: []
  logout: []
}>()

const avatarLetter = computed(() => {
  const n = (props.displayName || 'U').trim()
  return n ? n.charAt(0).toUpperCase() : 'U'
})
</script>

<style scoped>
.top-nav {
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  padding: 0 16px;
  justify-content: space-between;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.top-back-btn {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  padding: 0;
}

.top-back-btn:hover {
  background: #f5f5f5;
}

.nav-actions {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}

.user-info:hover {
  background: #f5f5f5;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--dp-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 500;
}

.user-name {
  font-size: 14px;
  color: #6b7280;
}

.settings-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 8px;
  min-width: 180px;
  display: none;
  z-index: 100;
}

.settings-menu.show {
  display: block;
}

.settings-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 8px;
}

.settings-item:hover {
  background: #f5f5f5;
}

.settings-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 8px 0;
}

.settings-item.logout {
  color: #6b7280;
}
</style>
