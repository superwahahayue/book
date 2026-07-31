import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import reveal from './directives/reveal'
import './styles/main.css'

// Restore theme before first paint to avoid a flash.
const saved = localStorage.getItem('theme')
if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
  document.documentElement.setAttribute('data-theme', 'dark')
}

createApp(App).use(router).directive('reveal', reveal).mount('#app')
