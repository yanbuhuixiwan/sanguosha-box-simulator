<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from './api'
import { useToast } from './composables/useToast'
import { inkBurstState } from './composables/useInkBurst'
import { useAuth } from './stores/auth'

const auth = useAuth()
const router = useRouter()
const { toasts, success: toastSuccess, error: toastError } = useToast()

const rechargeOpen = ref(false)
const recharging = ref(false)
const amount = ref(10000)

const navItems = [
  { to: '/', label: '大厅' },
  { to: '/treasure', label: '奇珍异宝' },
  { to: '/corridor', label: '梦之回廊' },
  { to: '/palace', label: '天宫宝库' },
  { to: '/shop', label: '商店' },
  { to: '/odds', label: '概率公示' },
  { to: '/inventory', label: '背包' },
  { to: '/stats', label: '战绩' },
]

const yuanbaoText = computed(() => auth.yuanbao.toLocaleString('zh-CN'))

onMounted(async () => {
  if (auth.token && !auth.ready) await auth.restore()
})

// 任何接口返回 401，都把 store 里的登录态收干净；要不要跳登录由下面的 watch 决定
function onUnauthorized() {
  auth.logout()
}
if (typeof window !== 'undefined') {
  window.addEventListener('sgs:unauthorized', onUnauthorized)
  onUnmounted(() => window.removeEventListener('sgs:unauthorized', onUnauthorized))
}

async function doRecharge() {
  recharging.value = true
  try {
    const res = await api.recharge(amount.value)
    auth.setYuanbao(res.yuanbao)
    toastSuccess(`充值成功，+${res.gained.toLocaleString('zh-CN')} 元宝（虚拟）`)
    rechargeOpen.value = false
  } catch (err) {
    toastError(err.message)
  } finally {
    recharging.value = false
  }
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}

// token 被 401 打掉时（过期 / 服务端换密钥），只在需要登录的页面把人送回登录页；
// /odds 这类公开页不打扰。主动点「退出」走 logout()，不受这里影响。
watch(
  () => auth.token,
  (token) => {
    if (token) return
    const cur = router.currentRoute.value
    if (cur.meta?.auth && cur.name !== 'login') {
      router.push({ name: 'login', query: { redirect: cur.fullPath } })
    }
  },
)
</script>

<template>
  <div class="app">
    <header v-if="auth.token" class="app-header">
      <div class="shell app-header__inner">
        <router-link to="/" class="brand">
          <span class="brand__mark">杀</span>
          <span>
            三国杀 · 盒子
            <span class="brand__sub">BOX SIMULATOR</span>
          </span>
        </router-link>

        <nav class="nav">
          <router-link v-for="item in navItems" :key="item.to" :to="item.to" class="nav__item">
            {{ item.label }}
          </router-link>
        </nav>

        <div class="wallet">
          <span class="wallet__icon">◈</span>
          <span>{{ yuanbaoText }}</span>
        </div>

        <button class="btn btn-sm btn-ghost" @click="rechargeOpen = true">补给</button>

        <button class="btn btn-sm btn-ghost" :title="auth.user?.username" @click="logout">
          退出
        </button>
      </div>
    </header>

    <main class="app-main">
      <router-view />
    </main>

    <!-- 充值弹窗 -->
    <div v-if="rechargeOpen" class="modal-mask" @click.self="rechargeOpen = false">
      <div class="modal" style="max-width: 420px">
        <div class="modal__head">
          <div>
            <h3 class="modal__title">元宝补给</h3>
            <p class="subtle" style="margin: 0.45rem 0 0">
              本模拟器不涉及任何真实支付，元宝纯属虚拟数据。
            </p>
          </div>
          <button class="modal__close" @click="rechargeOpen = false">✕</button>
        </div>

        <div class="grid grid-2" style="margin-bottom: 1.1rem">
          <button
            v-for="preset in [1000, 5000, 10000, 50000]"
            :key="preset"
            class="btn btn-sm"
            :class="amount === preset ? 'btn-gold' : 'btn-ghost'"
            @click="amount = preset"
          >
            {{ preset.toLocaleString('zh-CN') }}
          </button>
        </div>

        <div class="field">
          <label>自定义数量</label>
          <input v-model.number="amount" class="input" type="number" min="1" max="1000000" />
        </div>

        <div class="modal__foot">
          <button class="btn btn-gold" :disabled="recharging" @click="doRecharge">
            <span v-if="recharging" class="spinner" />
            {{ recharging ? '输送中' : '确认补给' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 泼墨转场：墨团从点击处炸开盖满屏幕，切页后再收墨 -->
    <div
      v-if="inkBurstState.active"
      class="ink-burst"
      :class="`ink-burst--${inkBurstState.phase}`"
      :style="{
        '--ox': `${(inkBurstState.x * 100).toFixed(2)}%`,
        '--oy': `${(inkBurstState.y * 100).toFixed(2)}%`,
      }"
      aria-hidden="true"
    >
      <span class="ink-burst__blob ink-burst__blob--a" />
      <span class="ink-burst__blob ink-burst__blob--b" />
      <span class="ink-burst__blob ink-burst__blob--c" />
      <span class="ink-burst__blob ink-burst__blob--d" />
      <span class="ink-burst__blob ink-burst__blob--e" />
      <span class="ink-burst__haze" />
    </div>

    <div class="toast-stack">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="`toast--${t.type}`">
        {{ t.message }}
      </div>
    </div>
  </div>
</template>
