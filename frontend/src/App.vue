<template>
  <div v-if="!authReady" class="app-boot">加载中…</div>
  <LoginView v-else-if="!currentUser" @success="onLoginSuccess" />
  <component :is="currentViewComp" v-else @navigate="handleNavigate" />
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { authReady, bootAuth, currentUser } from './auth/session'
import HomeView from './views/HomeView.vue'
import PersonalKbView from './views/PersonalKbView.vue'
import HistoryView from './views/HistoryView.vue'
import LoginView from './views/LoginView.vue'

type ViewName = 'home' | 'kb' | 'history'

const activeView = ref<ViewName>('home')

const currentViewComp = computed(() => {
  switch (activeView.value) {
    case 'kb':
      return PersonalKbView
    case 'history':
      return HistoryView
    case 'home':
    default:
      return HomeView
  }
})

const handleNavigate = (view: ViewName) => {
  activeView.value = view
}

const onLoginSuccess = () => {
  activeView.value = 'home'
}

const onGlobalUnauthorized = () => {
  activeView.value = 'home'
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
