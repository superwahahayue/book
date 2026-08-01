<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errMsg } from '@/api/client'
import { setCurrentUser } from '@/auth'

const router = useRouter()
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致。'
    return
  }
  submitting.value = true
  try {
    setCurrentUser(await api.register({ email: email.value, password: password.value }))
    router.replace({ name: 'library' })
  } catch (e) {
    error.value = errMsg(e, '注册失败，请稍后重试。')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="auth-page">
    <form class="auth-card card" @submit.prevent="submit">
      <p class="auth-kicker">开始创作</p>
      <h1>创建账号</h1>
      <p class="page-lead">你的故事、人物与章节仅对你可见。</p>
      <p v-if="error" class="alert err">{{ error }}</p>
      <label class="field">
        <span class="field-label">邮箱</span>
        <input v-model.trim="email" class="input" type="email" autocomplete="email" required maxlength="255">
      </label>
      <label class="field">
        <span class="field-label">密码</span>
        <input v-model="password" class="input" type="password" autocomplete="new-password" required minlength="8" maxlength="255">
        <span class="field-help">至少 8 个字符</span>
      </label>
      <label class="field">
        <span class="field-label">确认密码</span>
        <input v-model="confirmPassword" class="input" type="password" autocomplete="new-password" required minlength="8" maxlength="255">
      </label>
      <button class="btn btn-primary btn-block" :disabled="submitting">{{ submitting ? '正在注册…' : '注册并进入书库' }}</button>
      <p class="auth-switch">已有账号？<RouterLink to="/login">去登录</RouterLink></p>
    </form>
  </section>
</template>
