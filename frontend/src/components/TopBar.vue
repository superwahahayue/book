<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

const isDark = ref(false)

onMounted(() => {
  isDark.value = document.documentElement.dataset.theme === 'dark'
})

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.dataset.theme = isDark.value ? 'dark' : 'light'
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}
</script>

<template>
  <header class="topbar">
    <RouterLink to="/" class="brand" aria-label="剧情导演首页">
      <span class="brand-mark" aria-hidden="true">剧</span>
      <span>剧情导演</span>
    </RouterLink>
    <nav class="topbar-nav" aria-label="主导航">
      <RouterLink to="/" class="nav-link">书库</RouterLink>
      <RouterLink to="/create" class="nav-link nav-link--new">新建故事</RouterLink>
      <button type="button" class="icon-btn" :aria-label="isDark ? '切换浅色模式' : '切换深色模式'" @click="toggleTheme">
        {{ isDark ? '☀' : '◐' }}
      </button>
    </nav>
  </header>
</template>
