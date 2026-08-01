import { reactive } from 'vue'
import { api } from '@/api/client'

export const auth = reactive({
  user: null,
  loaded: false,
})

export async function loadCurrentUser() {
  try {
    auth.user = await api.currentUser()
  } catch (error) {
    if (error?.response?.status === 401) auth.user = null
    else throw error
  } finally {
    auth.loaded = true
  }
  return auth.user
}

export function setCurrentUser(user) {
  auth.user = user
  auth.loaded = true
}

export function clearCurrentUser() {
  auth.user = null
  auth.loaded = true
}
