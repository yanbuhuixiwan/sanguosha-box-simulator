import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './stores/auth'

const routes = [
  { path: '/', name: 'home', component: () => import('./views/HomeView.vue'), meta: { auth: true, title: '大厅' } },
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue'), meta: { title: '登录' } },
  // 盒子模拟器拆分出的三处玩法入口，抽盒子的功能收进「奇珍异宝」
  { path: '/treasure', name: 'treasure', component: () => import('./views/TreasureView.vue'), meta: { auth: true, title: '奇珍异宝' } },
  {
    path: '/corridor',
    name: 'corridor',
    component: () => import('./views/CorridorView.vue'),
    meta: { auth: true, title: '梦之回廊' },
  },
  {
    path: '/palace',
    name: 'palace',
    component: () => import('./views/PalaceView.vue'),
    meta: { auth: true, title: '天宫宝库' },
  },
  { path: '/box/:id', name: 'box', component: () => import('./views/BoxView.vue'), meta: { auth: true, title: '开盒' }, props: true },
  { path: '/recruit/:pool', name: 'recruit', component: () => import('./views/RecruitView.vue'), meta: { auth: true, title: '招募' }, props: true },
  { path: '/inventory', name: 'inventory', component: () => import('./views/InventoryView.vue'), meta: { auth: true, title: '背包' } },
  { path: '/shop', name: 'shop', component: () => import('./views/ShopView.vue'), meta: { auth: true, title: '商店' } },
  { path: '/stats', name: 'stats', component: () => import('./views/StatsView.vue'), meta: { auth: true, title: '战绩' } },
  { path: '/odds', name: 'odds', component: () => import('./views/OddsView.vue'), meta: { title: '概率公示' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.ready) await auth.restore()

  if (to.meta.auth && !auth.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.token) {
    return { name: 'home' }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 三国杀盒子模拟器` : '三国杀盒子模拟器'
})

export default router
