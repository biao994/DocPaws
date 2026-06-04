import { createRouter, createWebHistory } from 'vue-router'

import HistoryView from '../views/HistoryView.vue'
import HomeView from '../views/HomeView.vue'
import PersonalKbView from '../views/PersonalKbView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/kb', name: 'kb', component: PersonalKbView },
    { path: '/history', name: 'history', component: HistoryView },
    { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
  ],
})
