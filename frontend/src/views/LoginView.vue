<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errMsg } from '@/api/client'
import { auth, setCurrentUser } from '@/auth'

const router = useRouter()
const route = useRoute()
const email = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    setCurrentUser(await api.login({ email: email.value, password: password.value }))
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (e) {
    error.value = errMsg(e, '登录失败，请稍后重试。')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="auth-page">
    <form class="auth-card card" @submit.prevent="submit">
      <p class="auth-kicker">欢迎回来</p>
      <h1>登录剧情导演</h1>
      <p class="page-lead">登录后继续管理你的故事和分支。</p>
      <p v-if="auth.loadError" class="alert err">{{ auth.loadError }}</p>
      <p v-if="error" class="alert err">{{ error }}</p>
      <label class="field">
        <span class="field-label">邮箱</span>
        <input v-model.trim="email" class="input" type="email" autocomplete="email" required maxlength="255">
      </label>
      <label class="field">
        <span class="field-label">密码</span>
        <input v-model="password" class="input" type="password" autocomplete="current-password" required minlength="8" maxlength="255">
      </label>
      <button class="btn btn-primary btn-block" :disabled="submitting">{{ submitting ? '正在登录…' : '登录' }}</button>
      <p class="auth-switch">还没有账号？<RouterLink to="/register">立即注册</RouterLink></p>
    </form>
  </section>
</template>
