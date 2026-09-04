<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { auth, clearCurrentUser } from '@/auth'

const router = useRouter()
const isDark = ref(false)

onMounted(() => {
  isDark.value = document.documentElement.dataset.theme === 'dark'
})

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.dataset.theme = isDark.value ? 'dark' : 'light'
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

async function logout() {
  try {
    await api.logout()
  } finally {
    clearCurrentUser()
    router.push({ name: 'login' })
  }
}
</script>

<template>
  <header class="topbar">
    <RouterLink to="/" class="brand" aria-label="剧情导演首页">
      <span class="brand-mark" aria-hidden="true">剧</span>
      <span>剧情导演</span>
    </RouterLink>
    <nav class="topbar-nav" aria-label="主导航">
      <template v-if="auth.user">
        <RouterLink to="/" class="nav-link">书库</RouterLink>
        <RouterLink to="/create" class="nav-link nav-link--new">新建故事</RouterLink>
        <span class="account-email" :title="auth.user.email">
          {{ auth.user.email }}<small v-if="auth.user.is_admin">管理员</small>
        </span>
        <button type="button" class="nav-link" @click="logout">退出</button>
      </template>
      <template v-else>
        <RouterLink to="/login" class="nav-link">登录</RouterLink>
        <RouterLink to="/register" class="nav-link nav-link--new">注册</RouterLink>
      </template>
      <button type="button" class="icon-btn" :aria-label="isDark ? '切换浅色模式' : '切换深色模式'" @click="toggleTheme">
        {{ isDark ? '☀' : '◐' }}
      </button>
    </nav>
  </header>
</template>
