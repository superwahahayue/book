import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import http from './api/client'
import { clearCurrentUser } from './auth'
import reveal from './directives/reveal'
import './styles/main.css'

// Restore theme before first paint to avoid a flash.
const saved = localStorage.getItem('theme')
if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
  document.documentElement.setAttribute('data-theme', 'dark')
}

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      clearCurrentUser()
      const route = router.currentRoute.value
      if (route.meta.requiresAuth) {
        router.replace({ name: 'login', query: { redirect: route.fullPath } })
      }
    }
    return Promise.reject(error)
  },
)

createApp(App).use(router).directive('reveal', reveal).mount('#app')
