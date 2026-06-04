<template>
  <div v-if="!authReady" class="app-boot">加载中…</div>
  <LoginView v-else-if="!currentUser" @success="onLoginSuccess" />
  <RouterView v-else />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

import { authReady, bootAuth, currentUser } from './auth/session'
import LoginView from './views/LoginView.vue'

const router = useRouter()

const onLoginSuccess = () => {
  void router.replace({ name: 'home' })
}

const onGlobalUnauthorized = () => {
  void router.replace({ name: 'home' })
}

onMounted(async () => {
  window.addEventListener('docpaws:unauthorized', onGlobalUnauthorized)
  await bootAuth()
})

onUnmounted(() => {
  window.removeEventListener('docpaws:unauthorized', onGlobalUnauthorized)
})
</script>

<style>
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
}

.app-boot {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.95rem;
  color: #6b7280;
  background: #f9fafb;
}
</style>
