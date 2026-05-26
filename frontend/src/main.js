import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import { initThemeFromStorage } from './utils/theme'

initThemeFromStorage()
createApp(App).mount('#app')
