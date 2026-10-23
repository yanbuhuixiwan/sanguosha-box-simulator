import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, tokenStore } from '../api'

export const useAuth = defineStore('auth', () => {
  const token = ref(tokenStore.get())
  const user = ref(null)
  const loading = ref(false)
  const ready = ref(false)

  const isLoggedIn = computed(() => Boolean(token.value && user.value))
  const yuanbao = computed(() => user.value?.yuanbao ?? 0)

  function apply(payload) {
    token.value = payload.token
    user.value = payload.user
    tokenStore.set(payload.token)
  }

  async function login(username, password) {
    loading.value = true
    try {
      apply(await api.login(username, password))
      ready.value = true
    } finally {
      loading.value = false
    }
  }

  async function register(username, password, nickname) {
    loading.value = true
    try {
      apply(await api.register(username, password, nickname))
      ready.value = true
    } finally {
      loading.value = false
    }
  }

  async function restore() {
    if (!token.value) {
      ready.value = true
      return
    }
    try {
      user.value = await api.me()
    } catch {
      logout()
    } finally {
      ready.value = true
    }
  }

  async function refresh() {
    if (!token.value) return
    try {
      user.value = await api.me()
    } catch {
      /* 静默失败，不打断当前操作 */
    }
  }

  function setYuanbao(value) {
    if (user.value && typeof value === 'number') user.value.yuanbao = value
  }

  function logout() {
    token.value = ''
    user.value = null
    tokenStore.clear()
  }

  return { token, user, loading, ready, isLoggedIn, yuanbao, login, register, restore, refresh, setYuanbao, logout }
})
