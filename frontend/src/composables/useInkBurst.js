import { reactive } from 'vue'

/**
 * 浓墨泼开转场。
 *
 * 状态放在模块级，App.vue 负责渲染遮罩、HomeView 负责触发，
 * 这样即使触发页在动画途中被路由卸载，墨层依然在屏幕上，
 * 等到墨色盖满再切页，切完再慢慢收墨。
 */
export const inkBurstState = reactive({
  active: false,
  phase: 'in', // in = 泼开盖屏，out = 收墨
  x: 0.5,
  y: 0.5,
  busy: false,
})

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function prefersReduced() {
  return typeof window !== 'undefined'
    && window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export async function playInkBurst(router, to, ev) {
  if (inkBurstState.busy) return
  if (prefersReduced()) {
    router.push(to)
    return
  }

  inkBurstState.busy = true
  inkBurstState.x = ev ? ev.clientX / window.innerWidth : 0.5
  inkBurstState.y = ev ? ev.clientY / window.innerHeight : 0.5
  inkBurstState.phase = 'in'
  inkBurstState.active = true

  await wait(420) // 墨盖满
  try {
    await router.push(to)
  } catch {
    /* 重复导航忽略 */
  }
  await wait(90)
  inkBurstState.phase = 'out'
  await wait(540)
  inkBurstState.active = false
  inkBurstState.busy = false
}
