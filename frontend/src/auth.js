import { reactive } from 'vue'
import { api } from '@/api/client'

export const auth = reactive({
  user: null,
  loaded: false,
  loadError: '',
})

export async function loadCurrentUser() {
  try {
    auth.user = await api.currentUser()
    auth.loadError = ''
  } catch (error) {
    auth.user = null
    auth.loadError = error?.response?.status === 401
      ? ''
      : '暂时无法连接后端服务，请确认 API 已在 http://localhost:8000 启动。'
  } finally {
    auth.loaded = true
  }
  return auth.user
}

export function setCurrentUser(user) {
  auth.user = user
  auth.loaded = true
  auth.loadError = ''
}

export function clearCurrentUser() {
  auth.user = null
  auth.loaded = true
}
