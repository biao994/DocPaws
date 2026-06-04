import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'
import './style.css'
import { initThemeFromStorage } from './utils/theme'

initThemeFromStorage()
createApp(App).use(router).mount('#app')
