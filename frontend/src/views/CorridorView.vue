<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import ItemGlyph from '../components/ItemGlyph.vue'
import ResultModal from '../components/ResultModal.vue'
import { mediaUrl, focusPosition } from '../assets/media.js'
import { useToast } from '../composables/useToast'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const { success: toastSuccess, error: toastError } = useToast()

const data = ref(null)
const loading = ref(true)
const pulling = ref(false)
const buying = ref(false)
const result = ref(null)
const modalOpen = ref(false)
const flash = ref(new Set())
const brokeSkin = ref(false)
const listRef = ref(null)

// ---------------- 抽奖「光点逐格弹出」动效 ----------------
// 抽 N 次就在阵盘上依次弹 N 个光点，全部弹完才弹结算面板
const revealing = ref(false)
const revealLit = ref(new Set()) // 动画期间已经亮到的格子
const revealFlashId = ref(0) // 这一拍正在弹光点的格子
const revealFlashTick = ref(0) // 连着两发落在同一格时靠它重启动画
const revealIsNew = ref(false)
const revealDone = ref(0)
const revealTotal = ref(0)
let revealAllIds = []
let revealTimer = 0
let revealToken = 0
let revealResolve = null
let prevClaimed = 0 // 动画期间连线数先停在抽之前的数值
let prevClaimedIds = new Set() // 外圈奖励格同理：先亮抽之前已领的，播完再补亮
let prevPulls = 0 // 已抽次数同理，播完再跳
let prevPityLeft = 0
let prevRate = 0
const reduceMotion =
  typeof window !== 'undefined' &&
  !!window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// 期数按日期倒序展示（最新在上），并按年份分组
const periods = computed(() => [...(data.value?.periods || [])].reverse())
const activePeriod = computed(() => data.value?.id || '')
const isCurrent = computed(() => !!data.value?.is_current)

const owned = computed(() => data.value?.owned_cost_item ?? 0)
// 迷迭珠不够时不再把按钮置灰：点下去先弹「补给」弹层，买够自动接着抽
const canPull = () => !!data.value && !pulling.value && !data.value.finished
const canBuy = (n) => !!data.value && !buying.value && auth.yuanbao >= data.value.cost_price * n

// ---------------- 迷迭珠不足（游戏同款对话框） ----------------
const MUTE_KEY = 'corridor.supply.mute'
const supplyOpen = ref(false)
const pendingPull = ref(0) // 0 = 单纯补给；>0 = 买够后自动接着回忆这么多次
// 「本次登录不再提示」：勾上后再缺珠就直接买，不再弹框
const muteSupply = ref(
  typeof sessionStorage !== 'undefined' && sessionStorage.getItem(MUTE_KEY) === '1',
)
watch(muteSupply, (on) => {
  if (typeof sessionStorage === 'undefined') return
  if (on) sessionStorage.setItem(MUTE_KEY, '1')
  else sessionStorage.removeItem(MUTE_KEY)
})

const supplyNeedQty = computed(() => Math.max(1, pendingPull.value - owned.value))
/** 与游戏一致：一包 10 颗（3000 元宝）；元宝买不起 10 颗时按差额买 */
const supplyQty = computed(() => {
  const need = supplyNeedQty.value
  const price = data.value?.cost_price || 0
  return need >= 10 || auth.yuanbao < price * 10 ? need : 10
})
const supplyCost = computed(() => supplyQty.value * (data.value?.cost_price || 0))

function openSupply(count = 0) {
  pendingPull.value = count
  supplyOpen.value = true
}

function closeSupply() {
  supplyOpen.value = false
  pendingPull.value = 0
}

/** 弹框里点「确定」：买珠 → 关掉弹框 → 立刻把刚才那一次回忆掉 */
async function confirmSupply() {
  const want = pendingPull.value
  const ok = await buy(supplyQty.value)
  if (!ok) return
  supplyOpen.value = false
  pendingPull.value = 0
  if (!want) return
  await nextTick()
  const can = Math.min(owned.value, want)
  if (can > 0) await pull(can)
  if (can < want) openSupply(want - can) // 还是不够就再问一次
}

const litPct = computed(() =>
  data.value ? (shownLit.value / data.value.total_fragments) * 100 : 0,
)
const linePct = computed(() =>
  data.value ? (data.value.claimed_count / data.value.total_lines) * 100 : 0,
)

/** 动画期间阵盘只亮到当前这一发，播完才回到后端返回的最终态 */
const boardCells = computed(() => {
  const d = data.value
  if (!d) return []
  if (!revealing.value) return d.board
  return d.board.map((c) => ({ ...c, lit: revealLit.value.has(c.id) }))
})
const shownLit = computed(() =>
  revealing.value ? revealLit.value.size : data.value?.lit_count || 0,
)
const shownClaimed = computed(() =>
  revealing.value ? prevClaimed : data.value?.claimed_count || 0,
)
const shownPulls = computed(() => (revealing.value ? prevPulls : data.value?.pulls || 0))
const shownPityLeft = computed(() =>
  revealing.value ? prevPityLeft : data.value?.pity_remaining || 0,
)
const shownRate = computed(() =>
  revealing.value ? prevRate : data.value?.next_new_rate || 0,
)

/** 每个格子被几条已完成的连线穿过（用来给格子加一圈金光） */
const lineHits = computed(() => {
  const hits = new Map()
  // 光点还在弹的时候先不亮连线，等播完再一起亮
  if (!data.value || revealing.value) return hits
  for (const line of data.value.lines) {
    if (!line.claimed) continue
    for (const cell of line.cells) hits.set(cell, (hits.get(cell) || 0) + 1)
  }
  return hits
})

const lineGroups = computed(() => {
  const lines = data.value?.lines || []
  const diagLines = lines.filter((l) => l.id.startsWith('diag'))
  // 两条斜线的奖励通常不同（一条常是皮肤），只有完全相同时才合并成一行
  const diagSame =
    diagLines.length > 1 &&
    diagLines.every(
      (l) => l.reward?.key === diagLines[0].reward?.key && l.reward?.qty === diagLines[0].reward?.qty,
    )
  const diagItems = diagSame
    ? [
        {
          ...diagLines[0],
          id: 'diag-all',
          cells: [],
          note: '主对角 / 副对角',
          claimed: diagLines.every((l) => l.claimed),
          stateText: `已领 ${diagLines.filter((l) => l.claimed).length}/${diagLines.length}`,
        },
      ]
    : diagLines
  return [
    { key: 'row', title: '横向', items: lines.filter((l) => l.id.startsWith('row')) },
    { key: 'col', title: '纵向', items: lines.filter((l) => l.id.startsWith('col')) },
    { key: 'diag', title: '斜向（主对角 / 副对角）', items: diagItems },
  ]
})

/**
 * 奖励数量的展示文案：银币这类随机数量奖励（rand_qty=[1000,10000]）
 * 显示「×1000~10000（随机）」，其余正常显示 ×N（qty≤1 不显示数量）。
 */
const qtyLabel = (r) => {
  if (r.rand_qty?.length >= 2) return `×${r.rand_qty[0]}~${r.rand_qty[1]}（随机）`
  if (r.qty > 1) return `×${r.qty}`
  return ''
}

/**
 * 阵盘外圈 12 条连线的奖励格（与游戏内阵盘一致）：
 * 右侧一列是 5 条横线，底部一行是 5 条竖线，
 * 底部那一行的左右两端各一格，是两条斜线的奖励（有皮肤的期就摆在这里）。
 *   列 1 = 左斜线   ·  列 2~6 = 竖线 1~5   ·  列 7 = 右斜线
 */
const lineSlots = computed(() => {
  const lines = data.value?.lines || []
  const claimedOf = (l) => (revealing.value ? prevClaimedIds.has(l.id) : l.claimed)
  const pick = (id) => {
    const l = lines.find((x) => x.id === id)
    return l ? { ...l.reward, claimed: claimedOf(l), label: l.label, lineId: l.id } : null
  }
  return {
    side: [1, 2, 3, 4, 5].map((n) => pick(`row-${n}`)).filter(Boolean),
    bottom: [1, 2, 3, 4, 5].map((n) => pick(`col-${n}`)).filter(Boolean),
    diagLeft: pick('diag-1'),
    diagRight: pick('diag-2'),
  }
})

const rateRows = computed(() => {
  if (!data.value) return []
  const rates = data.value.fragment_rates || []
  return [0, 5, 10, 15, 20].map((start) => {
    const seg = rates.slice(start, start + 5)
    if (!seg.length) return null
    return {
      label: `第 ${start + 1}~${start + seg.length} 个碎片`,
      lo: Math.min(...seg),
      hi: Math.max(...seg),
    }
  }).filter(Boolean)
})

const finalArt = computed(() => {
  if (!data.value || brokeSkin.value) return ''
  return mediaUrl(data.value.final_prize.name, 'skin')
})

// ---------------- 盒子简介卡（仿官方盒子信息：名称 + 内含奖励） ----------------
const thumbStage = ref('skin') // skin → hero → none，逐级回退
const boxThumb = computed(() => {
  const d = data.value
  if (!d || thumbStage.value === 'none') return ''
  if (thumbStage.value === 'hero') return mediaUrl(d.hero, 'hero')
  return skinSrc.value || mediaUrl(d.hero, 'hero')
})
function onThumbError() {
  thumbStage.value = thumbStage.value === 'skin' ? 'hero' : 'none'
}

/**
 * 概率行：整数字去掉小数点后多余的 0（20% / 0.5% / 9.495%）
 */
const fmtPct = (p) => `${Number(p.toFixed(3)).toString()}%`
const totalPct = computed(() =>
  fmtPct((data.value?.draw_entries || []).reduce((s, e) => s + e.probability, 0)),
)

const cellName = (id) => data.value?.board.find((b) => b.id === id)?.name || ''

// 本期终极大奖皮肤图：阵盘点亮的格子按 5×5 拼图逐块显露这张图
// 素材命名规则是「皮肤·武将」（mediaUrl 内部拆成「武将_皮肤」查表）
// 本期大奖皮肤原画：只认「皮肤」这一类素材，绝不拿武将立绘顶替
// （以前兜底到武将图，导致神马超等新皮肤显示成武将原画，皮肤名与画面对不上）
const skinSrc = computed(() => {
  const d = data.value
  if (!d?.skin || !d?.hero) return ''
  return mediaUrl(`${d.skin}·${d.hero}`, 'skin')
})

/** 该期皮肤原画是否还没收录（有皮肤名但查不到图） */
const skinMissing = computed(() => {
  const d = data.value
  return !!d?.skin && !!d?.hero && !skinSrc.value
})

// 中央立绘：皮肤原画 → 终极大奖图 → 武将立绘（仅在没有皮肤图时占位，界面会标注）
const heroArt = computed(() => {
  const d = data.value
  if (!d) return ''
  return skinSrc.value || finalArt.value || mediaUrl(d.hero, 'hero')
})

/** 中央立绘正在用武将立绘占位（不是皮肤原画） */
const artFallback = computed(() => !!data.value && !skinSrc.value && !finalArt.value)

// 官方阵盘格子里印的是 1~99 的随机编号，这里按碎片 id 生成一个稳定的伪编号
// 阵盘编号固定 1~25，和游戏内从左到右、从上到下一致
const cellNo = (id) => id + 1

/** 本次获得的道具（结算条） */
const gained = computed(() => (result.value?.items || []).slice(0, 8))

async function load(period = '') {
  loading.value = !data.value
  try {
    data.value = await api.corridor(period)
    brokeSkin.value = false
    thumbStage.value = 'skin'
  } catch (err) {
    toastError(err.message)
  } finally {
    loading.value = false
  }
}

async function switchPeriod(id) {
  if (id === activePeriod.value || pulling.value) return
  result.value = null
  router.replace({ query: { ...route.query, period: id } })
  await load(id)
  scrollToActive()
}

/** 买迷迭珠。返回是否买到（供 confirmSupply 决定要不要接着回忆） */
async function buy(n) {
  if (!n || n <= 0 || buying.value) return false
  if (auth.yuanbao < (data.value?.cost_price || 0) * n) {
    toastError('元宝不足')
    return false
  }
  buying.value = true
  try {
    const res = await api.buyItem('bead_mi', n)
    auth.setYuanbao(res.yuanbao)
    data.value.owned_cost_item = res.owned
    toastSuccess(`购入「${res.name}」× ${res.count}，花费 ${res.spent.toLocaleString('zh-CN')} 元宝`)
    return true
  } catch (err) {
    toastError(err.message)
    return false
  } finally {
    buying.value = false
  }
}

function apply(res, { flashNew = true } = {}) {
  data.value.board = res.board
  data.value.lit_count = res.lit_count
  data.value.claimed_lines = res.claimed_lines
  data.value.next_new_rate = res.next_new_rate
  data.value.owned_cost_item = res.owned_cost_item
  data.value.finished = res.finished
  data.value.pulls = res.pulls
  data.value.pity_limit = res.pity_limit
  data.value.pity_remaining = res.pity_remaining
  data.value.lines = data.value.lines.map((line) => ({
    ...line,
    claimed: res.claimed_lines.includes(line.id),
  }))
  data.value.claimed_count = data.value.lines.filter((l) => l.claimed).length

  if (!flashNew) return // 光点动画自带反馈，不再重复抖一遍
  flash.value = new Set(res.new_fragment_ids)
  window.setTimeout(() => {
    flash.value = new Set()
  }, 1800)
}

function endReveal() {
  revealing.value = false
  revealFlashId.value = 0
  const done = revealResolve
  revealResolve = null
  if (done) done()
}

/** 点「跳过」：剩下的格子一次性点亮，直接进结算 */
function skipReveal() {
  if (!revealing.value) return
  revealToken++
  clearTimeout(revealTimer)
  const next = new Set(revealLit.value)
  for (const id of revealAllIds) next.add(id)
  revealLit.value = next
  revealDone.value = revealTotal.value
  endReveal()
}

/**
 * 逐发弹光点：抽几次就弹几次，弹完才 resolve（结算面板随后再开）。
 * 第一发停久一点让玩家看清，十连之后逐步加快，整体约 2 秒。
 */
function playReveal(res, prevLit) {
  const frags = res.fragments || []
  if (!frags.length || reduceMotion) return Promise.resolve()

  const token = ++revealToken
  revealAllIds = frags.map((f) => f.id)
  revealLit.value = new Set(prevLit)
  revealDone.value = 0
  revealTotal.value = frags.length
  revealFlashId.value = 0
  revealing.value = true

  return new Promise((resolve) => {
    revealResolve = resolve
    let i = 0
    const gap = (n) => (frags.length === 1 ? 520 : n === 1 ? 420 : 165)

    const step = () => {
      if (token !== revealToken) return // 已被跳过或页面切走
      if (i >= frags.length) {
        revealFlashId.value = 0
        revealTimer = window.setTimeout(() => {
          if (token === revealToken) endReveal()
        }, 300)
        return
      }
      const f = frags[i]
      const next = new Set(revealLit.value)
      next.add(f.id)
      revealLit.value = next
      revealFlashId.value = f.id
      revealFlashTick.value++
      revealIsNew.value = !!f.is_new
      revealDone.value = ++i
      revealTimer = window.setTimeout(step, gap(i))
    }
    step()
  })
}

async function pull(n) {
  if (pulling.value || revealing.value) return
  if (data.value?.finished) return // 集齐后大奖已发，后端也会拒绝
  if (owned.value < n) {
    const need = n - owned.value
    // 勾过「本次登录不再提示」且元宝够：直接买够差额再接着回忆，不弹框
    if (muteSupply.value && auth.yuanbao >= need * (data.value?.cost_price || 0)) {
      if (await buy(need)) return pull(n)
    }
    // 否则弹出游戏同款「迷迭珠不足」对话框，点确定买完自动回忆
    openSupply(n)
    return
  }
  pulling.value = true
  modalOpen.value = false
  try {
    const [res] = await Promise.all([
      api.corridorRecall(n, data.value.id),
      new Promise((r) => setTimeout(r, 360)),
    ])
    // 抽之前的进度：光点从旧盘面开始一格格往上点
    const prevLit = new Set((data.value.board || []).filter((c) => c.lit).map((c) => c.id))
    prevClaimed = data.value.claimed_count
    prevClaimedIds = new Set((data.value.lines || []).filter((l) => l.claimed).map((l) => l.id))
    prevPulls = data.value.pulls
    prevPityLeft = data.value.pity_remaining
    prevRate = data.value.next_new_rate

    apply(res, { flashNew: reduceMotion })
    result.value = res

    // ★ 先播光点（抽几次弹几次），播完才弹结算
    await playReveal(res, prevLit)

    modalOpen.value = true

    if (res.final_prize) {
      // 保底在十连中途就把 25 格补满时，后端会停止抽取并退回剩下的迷迭珠
      const extra = res.refunded ? `，退回 ${res.refunded} 颗迷迭珠` : ''
      toastSuccess(`回廊圆满！终极大奖「${res.final_prize.name}」已收入背包${extra}`)
    } else if (res.lines_completed.length) {
      toastSuccess(`连成 ${res.lines_completed.length} 条线，奖励已入包`)
    }
  } catch (err) {
    toastError(err.message)
  } finally {
    pulling.value = false
  }
}

// 支持 /corridor?period=corr-12 直接打开某一期
/** 77 期时把当前期滚到可视范围（窄屏是横向滚动，宽屏是纵向） */
async function scrollToActive() {
  await nextTick()
  const box = listRef.value
  const active = box?.querySelector('.period-item.is-active')
  if (!box || !active) return
  if (box.scrollWidth > box.clientWidth + 4) {
    const left = active.offsetLeft - box.offsetLeft
    box.scrollLeft = Math.max(0, left - box.clientWidth / 2 + active.clientWidth / 2)
  } else {
    const top = active.offsetTop - box.offsetTop
    box.scrollTop = Math.max(0, top - box.clientHeight / 2 + active.clientHeight / 2)
  }
}

onMounted(async () => {
  await load(String(route.query.period || ''))
  scrollToActive()
})

onUnmounted(() => {
  // 动效还在播就离开页面：停掉计时器并放掉 await，避免回调打到已卸载的组件
  revealToken++
  clearTimeout(revealTimer)
  revealing.value = false
  const done = revealResolve
  revealResolve = null
  if (done) done()
})
</script>

<template>
  <div class="shell corridor-page">
    <!-- 两侧「残简 · 画轴」气氛层：固定贴视口、不参与布局、不挡点击。
         只补结构，中间插画与棋盘一律不动。 -->
    <div class="ink-field" aria-hidden="true">
      <!-- 左：旧竹简侧缘的一道竖向枯笔 -->
      <span class="if if--edge-l"></span>
      <!-- 左：竹简横档细纹（列表间隙里的极淡横向） -->
      <span class="if if--fibre-l"></span>
      <!-- 底：横向墨沉积，先铺，右侧远山才不会被压掉 -->
      <span class="if if--floor"></span>
      <!-- 右：淡墨画轴边 + 宣纸纤维 -->
      <span class="if if--edge-r"></span>
      <!-- 右上：一条很淡的残旗 -->
      <span class="if if--flag"></span>
      <!-- 右：飞墨小点 -->
      <span class="if if--dust"></span>
      <span class="if if--seal if--seal-a">录</span>
      <span class="if if--seal if--seal-b">阅</span>
    </div>

    <div v-if="loading" class="empty">正在点亮回廊……</div>

    <template v-else-if="data">
      <!-- ================= 顶部资源条 ================= -->
      <header class="topbar">
        <router-link to="/" class="topbar__back" aria-label="返回大厅">‹</router-link>
        <h1 class="topbar__title">梦之回廊</h1>

        <div class="topbar__res">
          <span class="res-chip">
            <ItemGlyph name="迷迭珠" kind="item" rarity="epic" :size="16" />
            <b>{{ owned }}</b>
          </span>
          <span class="res-chip">
            <i class="res-chip__coin">¥</i>
            <b>{{ auth.yuanbao.toLocaleString('zh-CN') }}</b>
            <button
              class="res-chip__plus"
              :disabled="!canBuy(1)"
              title="花 300 元宝补给 1 颗迷迭珠"
              @click="buy(1)"
            >+</button>
          </span>
        </div>
      </header>

      <!-- ================= 回廊简介 ================= -->
      <section class="box-card">
        <p class="sec-label">回廊</p>
        <div class="box-card__body">
          <div class="box-card__thumb">
            <img
              v-if="boxThumb"
              :src="boxThumb"
              :alt="data.skin"
              :style="{ objectPosition: focusPosition('skin') }"
              @error="onThumbError"
            />
            <span v-else class="box-card__glyph">皮</span>
            <span class="box-card__badge">{{ data.label }}</span>
          </div>

          <div class="box-card__main">
            <h2 class="box-card__title">梦之回廊—{{ data.label }}</h2>
          </div>

          <div class="box-card__meta">
            <span class="box-card__chip">
              <ItemGlyph name="迷迭珠" kind="item" rarity="epic" :size="14" />
              {{ data.cost_price }} 元宝 / 颗
            </span>
            <span class="box-card__chip" title="模拟器为便于演示设定的兜底，非官方规则">模拟保底 {{ data.pity_limit }} 抽</span>
            <span class="box-card__chip">{{ data.dates }}</span>
          </div>
        </div>
      </section>

      <!-- ================= 主舞台 ================= -->
      <div class="stage">
        <!-- 左：期数列表（77 期，按年份分组、最新在上） -->
        <aside class="period-list" ref="listRef">
          <template v-for="(p, i) in periods" :key="p.id">
            <div
              v-if="i === 0 || periods[i - 1].dates.slice(0, 4) !== p.dates.slice(0, 4)"
              class="period-list__year"
            >
              {{ p.dates.slice(0, 4) }} 年
            </div>
            <button
              class="period-item"
              :class="{ 'is-active': p.id === activePeriod }"
              :title="`${p.skin} · ${p.hero} · ${p.dates}`"
              @click="switchPeriod(p.id)"
            >
              <span class="period-item__name">{{ p.skin }}</span>
              <span class="period-item__hero">{{ p.hero }}</span>
              <i v-if="p.current" class="period-item__dot" />
            </button>
          </template>
        </aside>

        <!-- 中：大奖立绘 -->
        <section class="hero-stage">
          <div
            class="hero-stage__art"
            :class="{ 'has-art': !!heroArt }"
            :style="heroArt ? { backgroundImage: `url(${heroArt})` } : null"
          />
          <div class="hero-stage__veil" aria-hidden="true" />

          <!-- 插画两侧：让立绘像从战场墨色里「破出」，极淡、不压主体 -->
          <span class="hero-wash hero-wash--l" aria-hidden="true"></span>
          <span class="hero-wash hero-wash--r" aria-hidden="true"></span>

          <p v-if="skinMissing" class="hero-stage__miss">
            皮肤原画暂未收录 · 此处为武将立绘
          </p>

          <div class="hero-stage__caption">
            <span class="super-plaque">超级奖励</span>
            <p class="hero-stage__skin">
              {{ data.skin }}<span class="hero-stage__hero">· {{ data.hero }}</span>
              <i class="seal-stamp seal-stamp--sm" aria-hidden="true">藏</i>
            </p>
            <p class="hero-stage__hint">
              收集全部记忆拼图，获得传说皮肤【{{ data.skin }}*{{ data.hero }}】
            </p>
          </div>

          <div class="hero-stage__meta">
            <span>{{ data.label }}</span>
            <span class="dot-sep">·</span>
            <span>{{ data.dates }}</span>
            <span v-if="!isCurrent" class="past-tag">往期 · 可回想</span>
            <span v-else class="live-tag">进行中</span>
          </div>
        </section>

        <!-- 右：记忆阵盘 -->
        <section class="board-stage">
          <div class="board-stage__head">
            <span class="board-stage__date">开放日期：{{ data.dates }}</span>
            <span class="board-stage__left">
              已集 {{ shownLit }}/{{ data.total_fragments }} · 连线 {{ shownClaimed }}/{{ data.total_lines }}
            </span>
          </div>
          <p class="board-stage__pity">
            <template v-if="data.finished">本期终极大奖已领取</template>
            <template v-else>
              模拟保底 <b>{{ data.pity_limit }}</b> 抽 · 已抽 <b>{{ shownPulls }}</b> 抽 · 再抽
              <b>{{ shownPityLeft }}</b> 抽必得
            </template>
          </p>
          <p class="board-stage__tip">
            每次回忆后获得随机奖励及随机记忆拼图，记忆拼图连线后将获得奖励
          </p>
          <p v-if="skinMissing" class="board-stage__tip board-stage__tip--warn">
            本期皮肤原画尚未收录，点亮的格子暂时以暗金格占位；补图后会自动拼成皮肤。
          </p>

          <div class="board-line">
            <div class="board">
              <div
                v-for="(cell, i) in boardCells"
                :key="cell.id"
                class="cell"
                :class="{
                  'is-lit': cell.lit,
                  'is-flash': flash.has(cell.id),
                  'on-line': lineHits.get(cell.id),
                  'has-img': cell.lit && !!skinSrc,
                  'is-spark-a': revealing && revealFlashId === cell.id && revealFlashTick % 2 === 0,
                  'is-spark-b': revealing && revealFlashId === cell.id && revealFlashTick % 2 === 1,
                }"
                :style="{
                  gridColumn: (i % 5) + 2,
                  gridRow: Math.floor(i / 5) + 1,
                  ...(cell.lit && skinSrc
                    ? {
                        backgroundImage: `url(${skinSrc})`,
                        backgroundSize: '500% 500%',
                        backgroundPosition: `${(i % 5) * 25}% ${Math.floor(i / 5) * 25}%`,
                      }
                    : {}),
                }"
                :title="cell.lit ? cell.name : `第 ${cellNo(cell.id)} 号拼图`"
              >
                <!-- 编号只给没点亮的格子提示位置；露出拼图后就不再压字 -->
                <span v-if="!cell.lit" class="cell__no">{{ cellNo(cell.id) }}</span>
                <!-- 点亮了但本期皮肤原画还没收录：用暗纹块占位，也不显示编号 -->
                <span v-else-if="!skinSrc" class="cell__void" />
                <!-- 这一发开出的是新碎片：光点上叠一个「新」字 -->
                <span
                  v-if="revealing && revealFlashId === cell.id && revealIsNew"
                  class="cell__new"
                >新</span>
              </div>

              <!-- 右侧一列：横线（第一行~第五行）的奖励，连成哪行亮哪格 -->
              <div
                v-for="(r, i) in lineSlots.side"
                :key="r.lineId"
                class="bonus"
                :class="{ 'is-claimed': r.claimed }"
                :style="{ gridColumn: 7, gridRow: i + 1 }"
                :title="`${r.label}奖励：${r.name} ${qtyLabel(r)}`"
              >
                <ItemGlyph :name="r.name" :kind="r.kind" :rarity="r.rarity" :size="20" />
                <span v-if="r.qty > 1" class="bonus__qty">×{{ r.qty }}</span>
              </div>

              <!-- 底部一行：竖线（第一列~第五列）的奖励，落在对应列的下方 -->
              <div
                v-for="(r, i) in lineSlots.bottom"
                :key="r.lineId"
                class="bonus"
                :class="{ 'is-claimed': r.claimed }"
                :style="{ gridColumn: i + 2, gridRow: 6 }"
                :title="`${r.label}奖励：${r.name} ${qtyLabel(r)}`"
              >
                <ItemGlyph :name="r.name" :kind="r.kind" :rarity="r.rarity" :size="20" />
                <span v-if="r.qty > 1" class="bonus__qty">×{{ r.qty }}</span>
              </div>

              <!-- 底部左右两端：两条斜线的奖励（有皮肤的期就摆在这里） -->
              <div
                v-for="(r, i) in [lineSlots.diagLeft, lineSlots.diagRight].filter(Boolean)"
                :key="r.lineId"
                class="bonus bonus--diag"
                :class="{ 'is-claimed': r.claimed, 'bonus--skin': r.kind === 'skin' }"
                :style="{ gridColumn: (r.lineId === 'diag-1' ? 1 : 7), gridRow: 6 }"
                :title="`${r.label}奖励：${r.name} ${qtyLabel(r)}`"
              >
                <ItemGlyph
                  :name="r.name"
                  :kind="r.kind"
                  :rarity="r.rarity"
                  :size="r.kind === 'skin' ? 24 : 20"
                />
                <span v-if="r.qty > 1" class="bonus__qty">×{{ r.qty }}</span>
              </div>
            </div>
          </div>

          <!-- 抽奖时按钮先让位给进度条：光点弹完才恢复 -->
          <div v-if="revealing" class="reveal-bar" @click="skipReveal">
            <span class="reveal-bar__orb" />
            <span class="reveal-bar__text">
              回忆中 <b>{{ revealDone }}</b>/{{ revealTotal }}
            </span>
            <span class="reveal-bar__skip">点击跳过</span>
          </div>
          <div v-else class="pull-row">
            <button class="pull-btn" :disabled="!canPull()" @click="pull(1)">
              <span class="pull-btn__cost">{{ data.finished ? '本期已集齐' : '消耗 迷迭珠 ×1' }}</span>
              <span class="pull-btn__label">{{ data.finished ? '大奖已领取' : '回忆 1 次' }}</span>
            </button>
            <button class="pull-btn pull-btn--ten" :disabled="!canPull()" @click="pull(10)">
              <span class="pull-btn__cost">{{ data.finished ? '本期已集齐' : '消耗 迷迭珠 ×10' }}</span>
              <span class="pull-btn__label">{{ data.finished ? '大奖已领取' : '回忆 10 次' }}</span>
            </button>
          </div>

          <p class="pull-hint">
            <span>现有迷迭珠 <b>{{ owned }}</b> 颗</span>
            <button class="pull-hint__buy" @click="openSupply(0)">补给 +</button>
          </p>

          <div class="board-stage__foot">
            <span>下次开出新碎片 <b class="gold">{{ shownRate.toFixed(2) }}%</b></span>
            <span v-if="data.finished" class="done-tag">本期已集齐</span>
            <span v-else>还差 <b class="gold">{{ Math.max(0, data.total_fragments - shownLit) }}</b> 种</span>
          </div>
        </section>
      </div>

      <!-- ================= 本次获得 ================= -->
      <!-- 光点还在弹的时候先不列结果，等播完再一起露出来 -->
      <section v-if="gained.length && !revealing" class="gain-bar">
        <span class="gain-bar__label">本次获得</span>
        <div class="gain-bar__items">
          <div v-for="it in gained" :key="it.key" class="gain-item">
            <div class="gain-item__art">
              <ItemGlyph :name="it.name" :kind="it.kind" :rarity="it.rarity" :size="26" />
              <span class="gain-item__qty">×{{ it.qty }}</span>
            </div>
            <span class="gain-item__name">{{ it.name }}</span>
          </div>
        </div>
        <button class="btn btn-sm btn-ghost" @click="modalOpen = true">查看结算</button>
      </section>

      <!-- ================= 详情 ================= -->
      <div class="detail-grid">
        <section class="panel panel--pad lines-panel">
          <div class="panel__head">
            <h3>十二连线</h3>
            <span class="subtle">{{ shownClaimed }} / {{ data.total_lines }} 已领</span>
          </div>
          <div class="line-groups">
            <div v-for="group in lineGroups" :key="group.key" class="line-group">
              <p class="line-group__title">{{ group.title }}</p>
              <div class="line-list">
                <div
                  v-for="line in group.items"
                  :key="line.id"
                  class="line-row"
                  :class="{ 'is-claimed': line.claimed }"
                >
                  <ItemGlyph
                    :name="line.reward.name"
                    :kind="line.reward.kind"
                    :rarity="line.reward.rarity"
                    :size="24"
                  />
                  <div class="line-row__main">
                    <span class="line-row__name">{{ line.reward.name }}</span>
                    <span class="line-row__cells subtle">{{
                      line.note || line.cells.map(cellName).join(' · ')
                    }}</span>
                  </div>
                  <span v-if="line.reward.kind !== 'skin' && line.reward.qty > 1" class="line-row__qty">×{{ line.reward.qty }}</span>
                  <span class="line-row__state">{{
                    line.stateText || (line.claimed ? '已领' : '未成线')
                  }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <div class="detail-side">
          <section class="panel panel--pad final-mini" :class="{ 'is-done': data.finished }">
            <div class="final-mini__art">
              <img
                v-if="finalArt"
                :src="finalArt"
                :alt="data.final_prize.name"
                :style="{ objectPosition: focusPosition('skin') }"
                loading="lazy"
                @error="brokeSkin = true"
              />
              <span v-else class="final-mini__glyph">皮</span>
              <span v-if="data.finished" class="final-mini__seal">已得</span>
            </div>
            <div class="final-mini__body">
              <p class="final-mini__eyebrow">回廊终点</p>
              <h3>{{ data.final_prize.name }}</h3>
              <p class="subtle">集齐 {{ data.total_fragments }} 种记忆碎片后获得，本期仅此一份。</p>
              <div class="final-mini__track">
                <div class="final-mini__fill" :style="{ width: `${litPct}%` }" />
              </div>
            </div>
          </section>

          <section class="panel panel--pad prob-panel">
            <div class="panel__head">
              <h3>概率</h3>
              <span class="subtle">{{ data.draw_entries.length }} 项 · 单次回想</span>
            </div>
            <div class="prob-list">
              <div
                v-for="e in data.draw_entries"
                :key="e.key"
                class="prob-row"
                :class="`r-${e.rarity}`"
              >
                <ItemGlyph :name="e.name" :kind="e.kind" :rarity="e.rarity" :size="24" />
                <span class="prob-row__name">{{ e.name }}<i v-if="qtyLabel(e)">{{ qtyLabel(e) }}</i></span>
                <span class="prob-row__pct">{{ fmtPct(e.probability) }}</span>
              </div>
              <div class="prob-row prob-row--sum">
                <span class="prob-row__sum">∑</span>
                <span class="prob-row__name">合计</span>
                <span class="prob-row__pct">{{ totalPct }}</span>
              </div>
            </div>
          </section>

          <section class="panel panel--pad">
            <div class="panel__head">
              <h3>碎片概率</h3>
              <span class="subtle">与累计碎片数相关</span>
            </div>
            <table class="rate-table">
              <thead>
                <tr><th>当前碎片数</th><th>开新碎片概率</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in rateRows" :key="row.label">
                  <td>{{ row.label }}</td>
                  <td>{{ row.lo.toFixed(2) }}% ~ {{ row.hi.toFixed(2) }}%</td>
                </tr>
              </tbody>
            </table>
            <p class="subtle rate-note">{{ data.fragment_rate_note }}</p>
          </section>

          <section class="panel panel--pad">
            <div class="panel__head"><h3>规则</h3></div>
            <ol class="rules">
              <li v-for="(rule, i) in data.rules" :key="i">{{ rule }}</li>
            </ol>
            <p class="subtle rules__src">
              规则、碎片概率与连线机制依据官网「梦之回廊」概率公示页面整理，仅作模拟演示。
            </p>
          </section>
        </div>
      </div>
    </template>

    <!-- ================= 迷迭珠不足（与游戏内对话框一致） ================= -->
    <div v-if="supplyOpen" class="modal-mask supply-mask" @click.self="closeSupply">
      <div class="supply-dialog">
        <p class="supply-dialog__line">你的迷迭珠不足 ^_^</p>
        <p class="supply-dialog__line">
          要花费 <span class="num">{{ supplyCost.toLocaleString('zh-CN') }}</span> 元宝购买
          <span class="num">{{ supplyQty }}</span> 个迷迭珠吗？
        </p>

        <div class="supply-dialog__acts">
          <button class="supply-btn supply-btn--cancel" :disabled="buying" @click="closeSupply">
            取消
          </button>
          <button class="supply-btn supply-btn--ok" :disabled="buying" @click="confirmSupply">
            {{ buying ? '购买中…' : '确定' }}
          </button>
        </div>

        <label class="supply-dialog__mute">
          <input v-model="muteSupply" type="checkbox" />
          <span>本次登录不再提示</span>
        </label>

        <p v-if="auth.yuanbao < supplyCost" class="supply-dialog__warn">
          元宝不足，可先去 <router-link to="/shop">商店</router-link> 补点元宝。
        </p>
      </div>
    </div>

    <ResultModal
      :open="modalOpen"
      :data="result"
      :title="data ? `${data.name} · ${data.theme}` : '梦之回廊'"
      :loading="pulling"
      :again-label="`再回忆 ${result?.count || 1} 次`"
      :again-disabled="!!data?.finished"
      @close="modalOpen = false"
      @again="pull(result?.count || 1)"
    />
  </div>
</template>

<style scoped>
.corridor-page {
  padding-top: 1rem;
}

/* ================= 顶栏 ================= */
.topbar {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.55rem 0.8rem;
  margin-bottom: 0.85rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.26);
  background-color: var(--ink-700);
  background-image: linear-gradient(180deg, rgba(45, 39, 32, 0.95), rgba(24, 21, 18, 0.97));
  overflow: hidden;
}
.topbar::after {
  content: '';
  position: absolute;
  left: 4%;
  right: 4%;
  top: 0;
  height: 2px;
  background-image: var(--tex-drybrush);
  background-repeat: repeat-x;
  background-size: 240px 16px;
  opacity: 0.2;
  pointer-events: none;
}
.topbar__back {
  flex: none;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 2px;
  font-size: 1.2rem;
  line-height: 1;
  color: var(--gold-2);
  border: 1px solid rgba(166, 124, 78, 0.3);
  background: rgba(14, 12, 10, 0.4);
}
.topbar__title {
  font-family: var(--font-brush);
  font-weight: 400;
  font-size: 1.15rem;
  letter-spacing: 0.16em;
  color: var(--paper);
  white-space: nowrap;
}
.topbar__res {
  margin-left: auto;
  display: flex;
  gap: 0.45rem;
}
/* 资源框＝竹简信息块 */
.res-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.5rem;
  border-radius: 2px;
  font-size: 0.78rem;
  font-family: var(--font-num);
  color: var(--paper-dim);
  border: 1px solid rgba(166, 124, 78, 0.26);
  background: rgba(18, 15, 13, 0.55);
}
.res-chip b { font-variant-numeric: tabular-nums; color: var(--paper); }
.res-chip__icon { width: 16px; height: 16px; object-fit: contain; }
/* 元宝＝水墨铜钱 */
.res-chip__coin {
  width: 15px;
  height: 15px;
  display: inline-grid;
  place-items: center;
  border-radius: 50%;
  font-style: normal;
  font-size: 0.6rem;
  color: #241a0e;
  background: radial-gradient(circle at 35% 30%, #d8bb8b, #a67c4e 70%, #7c5a34);
  border: 1px solid rgba(236, 226, 202, 0.28);
}
.res-chip__plus {
  width: 18px;
  height: 18px;
  margin-left: 2px;
  display: grid;
  place-items: center;
  border-radius: 2px;
  font-size: 0.75rem;
  line-height: 1;
  color: #f7e9d0;
  background: linear-gradient(160deg, #a8322b, #86201b);
}
.res-chip__plus:disabled { opacity: 0.42; }

/* ================= 盒子简介 ================= */
.sec-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0 0 0.4rem;
  font-family: var(--font-display);
  font-size: 0.8rem;
  letter-spacing: 0.16em;
  color: var(--paper-dim);
}
.sec-label::before {
  content: '';
  width: 3px;
  height: 0.86rem;
  border-radius: 0;
  background: var(--crimson);
}
.box-card { margin-bottom: 0.85rem; }
.box-card__body {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.55rem 0.7rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.24);
  background-color: var(--ink-700);
  background-image: linear-gradient(120deg, rgba(45, 39, 32, 0.95), rgba(22, 19, 16, 0.97));
  overflow: hidden;
}
.box-card__body::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.06;
  background-image: var(--tex-fiber);
  background-size: 180px 180px;
}
.box-card__thumb {
  position: relative;
  flex: none;
  width: 62px;
  height: 62px;
  border-radius: 2px;
  overflow: hidden;
  display: grid;
  place-items: center;
  border: 1px solid rgba(166, 124, 78, 0.4);
  background: rgba(18, 15, 13, 0.6);
}
.box-card__thumb img { width: 100%; height: 100%; object-fit: cover; object-position: 50% 12%; }
.box-card__glyph { font-family: var(--font-brush); color: var(--paper-dim); }
.box-card__badge {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 2px 0 1px;
  font-size: 0.52rem;
  text-align: center;
  color: var(--paper);
  background: linear-gradient(180deg, transparent, rgba(14, 12, 10, 0.86));
  text-shadow: 0 1px 2px #000;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.box-card__main { flex: 1; min-width: 0; }
.box-card__title {
  margin: 0;
  font-family: var(--font-brush);
  font-weight: 400;
  font-size: 1.1rem;
  letter-spacing: 0.06em;
  color: var(--paper);
}
.box-card__meta {
  flex: none;
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  justify-content: flex-end;
  max-width: 46%;
}
.box-card__chip {
  display: inline-flex;
  align-items: center;
  gap: 0.22rem;
  padding: 0.16rem 0.45rem;
  border-radius: 2px;
  font-size: 0.64rem;
  font-family: var(--font-num);
  color: var(--paper-dim);
  border: 1px solid rgba(166, 124, 78, 0.22);
  background: rgba(16, 13, 11, 0.4);
}

/* ================= 两侧气氛层：残简目录 · 墨框画轴 ================= */
/* 固定贴视口、z-index -1，压在内容之下，只在 shell 两侧的留白里显形 */
.ink-field {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  overflow: hidden;
}
.if { position: absolute; display: block; pointer-events: none; }

/* 左：从顶到底的一道竖向枯笔，粗细断续，左缘压重 */
.if--edge-l {
  left: 0;
  top: 0;
  bottom: 0;
  width: clamp(56px, 8.2vw, 118px);
  background-image:
    linear-gradient(
      180deg,
      transparent 0%,
      rgba(217, 198, 164, 0.13) 5%,
      rgba(217, 198, 164, 0.09) 46%,
      rgba(217, 198, 164, 0.05) 78%,
      transparent 97%
    ),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='64' height='720' viewBox='0 0 64 720' preserveAspectRatio='none'%3E%3Cdefs%3E%3ClinearGradient id='eg' x1='0' y1='0' x2='1' y2='0'%3E%3Cstop offset='0' stop-color='%23000000' stop-opacity='.44'/%3E%3Cstop offset='.42' stop-color='%23000000' stop-opacity='.17'/%3E%3Cstop offset='1' stop-color='%23000000' stop-opacity='0'/%3E%3C/linearGradient%3E%3Cfilter id='ef' x='-40%25' y='-4%25' width='180%25' height='108%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.045 0.008' numOctaves='4' seed='23' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='13' xChannelSelector='R' yChannelSelector='G'/%3E%3CfeGaussianBlur stdDeviation='.55'/%3E%3C/filter%3E%3C/defs%3E%3Crect width='64' height='720' fill='url(%23eg)'/%3E%3Cg filter='url(%23ef)' fill='%23d9c6a4'%3E%3Crect x='1.5' y='12' width='6.8' height='168' opacity='.14'/%3E%3Crect x='9.5' y='82' width='4' height='112' opacity='.085'/%3E%3Crect x='2' y='196' width='8.4' height='78' opacity='.12'/%3E%3Crect x='26' y='212' width='4.6' height='148' opacity='.055'/%3E%3Crect x='1.6' y='288' width='5.6' height='212' opacity='.11'/%3E%3Crect x='17' y='362' width='3.4' height='104' opacity='.06'/%3E%3Crect x='2.4' y='514' width='7.6' height='62' opacity='.125'/%3E%3Crect x='21' y='528' width='4' height='104' opacity='.055'/%3E%3Crect x='1.8' y='612' width='6' height='94' opacity='.105'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 1.6px 100%, 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.78;
  -webkit-mask-image: linear-gradient(90deg, #000 0 22%, rgba(0, 0, 0, 0.5) 58%, transparent 100%);
  mask-image: linear-gradient(90deg, #000 0 22%, rgba(0, 0, 0, 0.5) 58%, transparent 100%);
}

/* 左：竹简横档细纹，只出现在列表那一段，极淡 */
.if--fibre-l {
  left: 0;
  top: 13vh;
  height: 56vh;
  width: clamp(50px, 6.2vw, 92px);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='420' viewBox='0 0 80 420' preserveAspectRatio='none'%3E%3Cdefs%3E%3Cfilter id='ff' x='-10%25' y='-20%25' width='120%25' height='140%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.02 0.09' numOctaves='3' seed='7' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='2.6' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23ff)' fill='%23d9c6a4'%3E%3Crect x='2' y='18' width='62' height='1.1' opacity='.11'/%3E%3Crect x='2' y='66' width='54' height='1' opacity='.085'/%3E%3Crect x='2' y='114' width='66' height='1.1' opacity='.105'/%3E%3Crect x='2' y='162' width='48' height='1' opacity='.08'/%3E%3Crect x='2' y='210' width='60' height='1.1' opacity='.108'/%3E%3Crect x='2' y='258' width='52' height='1' opacity='.082'/%3E%3Crect x='2' y='306' width='64' height='1.1' opacity='.1'/%3E%3Crect x='2' y='354' width='46' height='1' opacity='.078'/%3E%3Crect x='2' y='398' width='58' height='1.1' opacity='.096'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.9;
  -webkit-mask-image: linear-gradient(90deg, #000 0 40%, rgba(0, 0, 0, 0.4) 74%, transparent 100%);
  mask-image: linear-gradient(90deg, #000 0 40%, rgba(0, 0, 0, 0.4) 74%, transparent 100%);
}

/* 右：淡墨画轴边 —— 竖向晕染 + 一点宣纸纤维 */
.if--edge-r {
  right: 0;
  top: 6vh;
  bottom: 3vh;
  width: clamp(104px, 13vw, 232px);
  background-image:
    radial-gradient(80% 34% at 84% 30%, rgba(198, 178, 142, 0.1), transparent 82%),
    radial-gradient(72% 42% at 92% 72%, rgba(166, 124, 78, 0.085), transparent 84%),
    linear-gradient(270deg, rgba(214, 196, 162, 0.055), rgba(12, 10, 8, 0.16) 58%, transparent 92%);
  background-size: 100% 100%, 100% 100%, 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.88;
  -webkit-mask-image: linear-gradient(270deg, #000 0 26%, rgba(0, 0, 0, 0.5) 62%, transparent 96%);
  mask-image: linear-gradient(270deg, #000 0 26%, rgba(0, 0, 0, 0.5) 62%, transparent 96%);
}

/* 右上：一条克制的残旗（按 1:1 像素画，缩放不会掉线） */
/* 极淡宣纸竖丝：窄条 + 小瓦片 repeat-y，避免整块噪声被拉伸 */
.if--edge-r::before {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 26%;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='120' viewBox='0 0 56 120'%3E%3Cdefs%3E%3Cfilter id='sf' x='-30%25' y='-10%25' width='160%25' height='120%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05 0.008' numOctaves='3' seed='5' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='5' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23sf)' fill='%23e6d6b6'%3E%3Crect x='40' y='0' width='.7' height='120' opacity='.05'/%3E%3Crect x='48' y='0' width='.9' height='120' opacity='.038'/%3E%3Crect x='33' y='0' width='.6' height='120' opacity='.03'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 56px 120px;
  background-repeat: repeat-y;
  opacity: 0.9;
  -webkit-mask-image: linear-gradient(270deg, #000, transparent 86%);
  mask-image: linear-gradient(270deg, #000, transparent 86%);
}
.if--flag {
  right: clamp(6px, 1.8vw, 34px);
  top: 7vh;
  width: clamp(38px, 4.2vw, 64px);
  height: clamp(116px, 18vh, 190px);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='232' viewBox='0 0 80 232' preserveAspectRatio='none'%3E%3Cg fill='none' stroke='%23e6d6b6' stroke-linecap='round' opacity='.16'%3E%3Cpath d='M62 232 L57 8' stroke-width='2.4'/%3E%3Cpath d='M57 30 C44 25 35 35 25 29 C27 51 25 70 23 92 C36 86 47 94 58 88' stroke-width='2'/%3E%3Cpath d='M57 152 C48 149 42 155 36 152' stroke-width='1.6'/%3E%3C/g%3E%3Cg fill='%23e6d6b6' opacity='.06'%3E%3Cpath d='M25 29 L32 36 L27 47 L35 49 L28 61 L23 55 Z'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.92;
  transform: rotate(-1.4deg);
  transform-origin: right bottom;
}

/* 右：3 颗飞墨小点，只是空气里的尘 */
.if--dust {
  right: 0.4vw;
  top: 28%;
  width: clamp(66px, 8.4vw, 132px);
  height: 32vh;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='280' viewBox='0 0 140 280' preserveAspectRatio='none'%3E%3Cg fill='%23e6d6b6'%3E%3Ccircle cx='112' cy='34' r='2.6' opacity='.3'/%3E%3Ccircle cx='62' cy='126' r='1.8' opacity='.22'/%3E%3Ccircle cx='124' cy='212' r='2.1' opacity='.26'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.86;
}

/* 底：横向墨沉积，下方略暗、上方渐隐，减少悬浮感 */
.if--floor {
  left: 0;
  right: 0;
  bottom: 0;
  height: clamp(120px, 20vh, 236px);
  background-image:
    var(--tex-ridge),
    var(--tex-brush-h),
    linear-gradient(
      to top,
      rgba(8, 7, 5, 0.46) 0%,
      rgba(11, 9, 7, 0.2) 40%,
      rgba(15, 12, 9, 0.05) 74%,
      transparent 100%
    );
  background-size: 100% 46%, 100% 26px, 100% 100%;
  background-position: left bottom, left 34%, 0 0;
  background-repeat: no-repeat;
  opacity: 0.84;
}

/* 两枚极小朱砂闲章：录 / 阅 */
.if--seal {
  padding: 3px 4px;
  font-family: var(--font-brush);
  font-size: 12px;
  line-height: 1;
  color: #f0dcbe;
  background: linear-gradient(158deg, #a8322b, #86201b);
  border-radius: 1px;
  box-shadow: inset 0 0 0 1px rgba(240, 220, 190, 0.3);
}
.if--seal-a { left: clamp(5px, 1.2vw, 20px); top: 12vh; transform: rotate(-4.5deg); opacity: 0.3; }
.if--seal-b { right: clamp(5px, 1.3vw, 22px); bottom: 5vh; transform: rotate(3.5deg); opacity: 0.2; }

/* ================= 主舞台 ================= */
.stage {
  display: grid;
  grid-template-columns: 122px minmax(0, 1fr) 332px;
  gap: 0.75rem;
  align-items: stretch;
}

/* 左：期数 */
.period-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  max-height: 470px;
  overflow-y: auto;
  padding-right: 2px;
}
.period-list__year {
  margin: 0.32rem 0 0.06rem;
  padding-left: 0.2rem;
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  color: var(--paper-mute);
}
.period-list__year:first-child { margin-top: 0; }
/* 竖版残简：左边一道朱砂枯笔就是选中标记，不再用亮金高亮 */
.period-item {
  position: relative;
  padding: 0.42rem 0.5rem;
  border-radius: 1px;
  text-align: left;
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  color: var(--paper-dim);
  border: 1px solid rgba(166, 124, 78, 0.18);
  background: linear-gradient(100deg, rgba(58, 50, 42, 0.72), rgba(30, 26, 22, 0.86));
  transition: 0.16s;
}
.period-item:hover { border-color: rgba(166, 124, 78, 0.44); color: var(--paper); }
.period-item.is-active {
  color: var(--paper);
  border-color: rgba(166, 124, 78, 0.44);
  background: linear-gradient(100deg, rgba(70, 58, 44, 0.85), rgba(36, 31, 26, 0.9));
}
.period-item.is-active::before {
  content: '';
  position: absolute;
  left: -1px;
  top: 10%;
  bottom: 10%;
  width: 3px;
  background: linear-gradient(180deg, transparent, var(--crimson-2) 16%, var(--crimson) 62%, rgba(158, 43, 37, 0.25) 92%, transparent);
}
.period-item__name { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.period-item__hero {
  display: block;
  margin-top: 0.04rem;
  font-family: var(--font-sans);
  font-size: 0.58rem;
  letter-spacing: 0.04em;
  color: var(--paper-mute);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.period-item.is-active .period-item__hero { color: var(--paper-dim); }
.period-item__dot {
  position: absolute;
  right: 5px;
  top: 50%;
  width: 5px;
  height: 5px;
  margin-top: -2.5px;
  border-radius: 50%;
  background: var(--crimson-2);
}

/* 中：立绘（不均匀干墨外框）*/
.hero-stage {
  position: relative;
  min-height: 470px;
  border-radius: 2px;
  overflow: hidden;
  border: 1px solid rgba(166, 124, 78, 0.34);
  background: #17130f;
  box-shadow: inset 0 0 44px -18px rgba(0, 0, 0, 0.92);
}
/* 四边墨线粗细不一致，像手抹的干墨框 */
.hero-stage::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 4;
  box-shadow:
    inset 2px 0 0 rgba(18, 15, 12, 0.55),
    inset 0 3px 0 rgba(18, 15, 12, 0.42),
    inset -3px 0 0 rgba(18, 15, 12, 0.5),
    inset 0 -2px 0 rgba(18, 15, 12, 0.48);
}
.hero-stage__art {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: 50% 12%;
  opacity: 0;
  transform: scale(1.02);
  transition: opacity 0.5s;
}
.hero-stage__art.has-art { opacity: 1; }
.hero-stage__veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, transparent 42%, rgba(23, 19, 15, 0.72) 78%, rgba(20, 17, 14, 0.92) 100%),
    linear-gradient(90deg, rgba(20, 17, 14, 0.46), transparent 28%, transparent 72%, rgba(20, 17, 14, 0.46));
}
/* 插画两侧：一条斜向枯墨痕 + 一小片淡墨晕，让立绘从战场墨色里破出 */
.hero-wash { position: absolute; pointer-events: none; z-index: 1; }
/* 左下：3 段带弧度的斜笔，越往外越细，深墨压在亮调插画上 */
.hero-wash--l {
  left: 0;
  bottom: 31%;
  width: 44%;
  height: 44%;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='170' viewBox='0 0 240 170' preserveAspectRatio='none'%3E%3Cdefs%3E%3Cfilter id='hw' x='-20%25' y='-60%25' width='140%25' height='220%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.03 0.09' numOctaves='3' seed='11' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='4' xChannelSelector='R' yChannelSelector='G'/%3E%3CfeGaussianBlur stdDeviation='.6'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23hw)' stroke='%230c0906' fill='none' stroke-linecap='butt'%3E%3Cpath d='M-6 146 C 40 126 86 100 140 70' stroke-width='12' opacity='.28'/%3E%3Cpath d='M148 66 C 174 54 198 40 226 24' stroke-width='7' opacity='.21'/%3E%3Cpath d='M8 158 C 44 144 74 130 108 112' stroke-width='3.6' opacity='.16'/%3E%3C/g%3E%3Cg filter='url(%23hw)' stroke='%23e6d6b6' fill='none' stroke-linecap='butt'%3E%3Cpath d='M-4 141 C 42 121 88 95 142 65' stroke-width='3.2' opacity='.13'/%3E%3Cpath d='M150 61 C 176 49 200 36 228 20' stroke-width='2.2' opacity='.1'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  -webkit-mask-image: radial-gradient(92% 98% at 20% 78%, #000 20%, transparent 90%);
  mask-image: radial-gradient(92% 98% at 20% 78%, #000 20%, transparent 90%);
  opacity: 0.9;
}
/* 右上：一小片淡墨晕 */
.hero-wash--r {
  right: 0;
  top: 0;
  width: 40%;
  height: 36%;
  background: radial-gradient(66% 66% at 80% 22%, rgba(14, 10, 7, 0.5), transparent 78%);
  opacity: 0.86;
}

/* 皮肤原画缺失时的说明角标：不让人把武将立绘当成皮肤 */
.hero-stage__miss {
  position: absolute;
  top: 0.6rem;
  right: 0.6rem;
  margin: 0;
  padding: 0.16rem 0.5rem;
  font-size: 0.6rem;
  letter-spacing: 0.04em;
  color: var(--gold-2);
  background: rgba(20, 17, 14, 0.82);
  border: 1px solid rgba(166, 124, 78, 0.36);
  border-radius: 2px;
}
/* 底部标题条：半透旧宣纸蒙层，不再是渐变黑块 */
.hero-stage__caption {
  position: absolute;
  left: 0.9rem;
  right: 0.9rem;
  bottom: 2.1rem;
  padding: 0.5rem 0.65rem 0.45rem;
  border-left: 2px solid rgba(158, 43, 37, 0.78);
  background: linear-gradient(180deg, rgba(236, 226, 202, 0.11), rgba(236, 226, 202, 0.035));
}
/* 超级奖励＝朱砂小印 */
.super-plaque {
  display: inline-block;
  padding: 1px 9px;
  border-radius: 1px;
  font-family: var(--font-brush);
  font-size: 0.8rem;
  letter-spacing: 0.16em;
  color: #f7e9d0;
  background: linear-gradient(158deg, #a8322b, #86201b);
  box-shadow: inset 0 0 0 1px rgba(247, 233, 208, 0.35);
  transform: rotate(-2deg);
}
.hero-stage__skin {
  margin: 0.4rem 0 0.15rem;
  font-family: var(--font-brush);
  font-weight: 400;
  font-size: clamp(1.15rem, 2.4vw, 1.6rem);
  letter-spacing: 0.06em;
  color: #f4e8ce;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.85);
}
.hero-stage__skin .seal-stamp {
  margin-left: 0.45rem;
  vertical-align: 0.18em;
}
.hero-stage__hero { color: var(--gold-2); font-size: 0.86em; }
.hero-stage__hint {
  margin: 0;
  font-size: 0.72rem;
  line-height: 1.55;
  color: var(--paper-dim);
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
}
.hero-stage__meta {
  position: absolute;
  left: 0.9rem;
  bottom: 0.7rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.68rem;
  color: var(--paper-mute);
}
.dot-sep { color: #6b5c42; }
.live-tag {
  padding: 0 6px;
  border-radius: 1px;
  color: #dfe6d2;
  background: rgba(110, 122, 98, 0.28);
  border: 1px solid rgba(110, 122, 98, 0.55);
}
.past-tag {
  padding: 0 6px;
  border-radius: 1px;
  color: var(--paper-dim);
  background: rgba(166, 124, 78, 0.12);
  border: 1px solid rgba(166, 124, 78, 0.36);
}

/* 右：阵盘 */
.board-stage {
  align-self: start;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  padding: 0.65rem 0.7rem 0.7rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.3);
  background-color: var(--ink-700);
  background-image: linear-gradient(180deg, rgba(45, 39, 32, 0.97), rgba(22, 19, 16, 0.98));
}
.board-stage__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.4rem;
  font-size: 0.66rem;
  font-family: var(--font-num);
  color: var(--paper-dim);
}
.board-stage__date { color: var(--gold-2); }
.board-stage__left { color: var(--paper-mute); }
/* 保底提示条：墨痕分割，去掉金色渐变条 */
.board-stage__pity {
  margin: 0;
  padding: 0.24rem 0.5rem;
  font-size: 0.64rem;
  letter-spacing: 0.04em;
  color: var(--paper-dim);
  border-radius: 1px;
  border-left: 2px solid rgba(158, 43, 37, 0.7);
  background: rgba(20, 17, 14, 0.5);
}
.board-stage__pity b { color: var(--gold-2); font-weight: 700; font-variant-numeric: tabular-nums; }
.board-stage__tip {
  margin: 0;
  font-size: 0.62rem;
  line-height: 1.5;
  color: var(--paper-mute);
}
.board-stage__tip--warn { margin-top: 0.15rem; color: var(--gold-2); }

.board-line {
  display: flex;
  gap: 0.45rem;
  align-items: stretch;
}
/* 阵盘：底色就是墨，格子之间的 3px 缝自然成了细枯墨分割线 */
.board {
  flex: 1;
  display: grid;
  /* 7×6：中间 5×5 是拼图阵盘，第 7 列放横线奖励、第 6 行放竖线奖励，
     第 6 行最左/最右两格是两条斜线的奖励（与游戏内阵盘一致） */
  grid-template-columns: repeat(7, minmax(0, 1fr));
  grid-template-rows: repeat(6, auto);
  gap: 3px;
  padding: 4px;
  border-radius: 1px;
  border: 1px solid rgba(166, 124, 78, 0.28);
  background: rgba(14, 12, 10, 0.62);
}
/* 未解锁格：浅宣纸底 + 细枯墨边，圆角几乎为零 */
.cell {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 1px;
  display: grid;
  place-items: center;
  overflow: hidden;
  font-size: 0.72rem;
  font-family: var(--font-num);
  font-variant-numeric: tabular-nums;
  color: #7a6544;
  border: 1px solid rgba(120, 104, 80, 0.42);
  background: linear-gradient(180deg, #ece2c8, #d8caa8);
  transition: 0.2s;
}
.cell__no { line-height: 1; opacity: 0.8; }
/* 已点亮但本期皮肤原画尚未收录：不留编号，用赭石菱纹占位 */
.cell__void {
  width: 8px;
  height: 8px;
  border: 1px solid rgba(122, 90, 52, 0.8);
  transform: rotate(45deg);
  opacity: 0.85;
}
/* 已解锁：赭石渍感（不会盖住拼图，只在没图的格子上铺） */
.cell.is-lit:not(.has-img) {
  background: linear-gradient(180deg, #c3a87c, #97794a);
  border-color: rgba(122, 90, 52, 0.8);
}
.cell.is-lit:not(.has-img)::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(58% 48% at 28% 72%, rgba(104, 70, 32, 0.32), transparent 70%),
    radial-gradient(44% 44% at 76% 22%, rgba(104, 70, 32, 0.2), transparent 72%);
}
.cell.is-lit:not(.has-img) .cell__void {
  width: 46%;
  height: 46%;
  border: 1px solid rgba(236, 226, 202, 0.32);
  border-radius: 1px;
  transform: none;
  opacity: 1;
}
.cell.has-img {
  border-color: rgba(166, 124, 78, 0.75);
  background-size: 500% 500%;
  background-repeat: no-repeat;
}
.cell.has-img .cell__no {
  position: absolute;
  top: 1px;
  left: 3px;
  font-size: 0.58rem;
  color: #fff;
  opacity: 0.9;
  text-shadow: 0 1px 2px #000;
}
.cell__name {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 0 2px;
  font-size: 0.56rem;
  line-height: 1.3;
  text-align: center;
  color: #fff;
  background: linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.72));
  text-shadow: 0 1px 2px #000;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 连线中的格子：一圈赭石弱描边，不发光 */
.cell.on-line {
  border-color: var(--gold-2);
  box-shadow: inset 0 0 0 1px rgba(201, 164, 110, 0.55);
}
.cell.is-flash { animation: cellPop 0.6s ease-out 2; }
@keyframes cellPop {
  0% { transform: scale(1); }
  35% { transform: scale(1.12); }
  100% { transform: scale(1); }
}

/* ---------- 抽奖回响：改成朱砂墨点逐格洇开 ---------- */
.cell.is-spark-a::after,
.cell.is-spark-b::after {
  content: '';
  position: absolute;
  inset: -40%;
  z-index: 2;
  pointer-events: none;
  background: radial-gradient(
    circle at 50% 50%,
    rgba(247, 233, 208, 0.95) 0%,
    rgba(201, 164, 110, 0.82) 15%,
    rgba(158, 43, 37, 0.45) 33%,
    rgba(158, 43, 37, 0) 62%
  );
  animation: revealSparkA 0.62s ease-out forwards;
}
.cell.is-spark-b::after { animation-name: revealSparkB; }

/* 外扩光环：一圈赭石细线往外涨 */
.cell.is-spark-a::before,
.cell.is-spark-b::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 3;
  border-radius: 2px;
  border: 1px solid rgba(201, 164, 110, 0.95);
  box-shadow: inset 0 0 0 1px rgba(201, 164, 110, 0.4);
  animation: revealRingA 0.56s ease-out forwards;
}
.cell.is-spark-b::before { animation-name: revealRingB; }

/* 两份同样的关键帧：连着两发落在同一格时靠换名字重启动画 */
@keyframes revealSparkA {
  0% { opacity: 0; transform: scale(0.22); }
  24% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(1.55); }
}
@keyframes revealSparkB {
  0% { opacity: 0; transform: scale(0.22); }
  24% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(1.55); }
}
@keyframes revealRingA {
  0% { opacity: 0; transform: scale(0.72); }
  20% { opacity: 1; transform: scale(0.98); }
  100% { opacity: 0; transform: scale(1.3); }
}
@keyframes revealRingB {
  0% { opacity: 0; transform: scale(0.72); }
  20% { opacity: 1; transform: scale(0.98); }
  100% { opacity: 0; transform: scale(1.3); }
}

.cell.is-spark-a,
.cell.is-spark-b {
  z-index: 1;
  border-color: var(--gold-2);
  box-shadow: inset 0 0 0 1px rgba(201, 164, 110, 0.65);
  animation: revealLiftA 0.5s ease-out;
}
.cell.is-spark-b { animation-name: revealLiftB; }
@keyframes revealLiftA {
  0% { transform: scale(1); }
  32% { transform: scale(1.1); }
  100% { transform: scale(1); }
}
@keyframes revealLiftB {
  0% { transform: scale(1); }
  32% { transform: scale(1.1); }
  100% { transform: scale(1); }
}

/* 新碎片角标＝朱砂小印 */
.cell__new {
  position: absolute;
  top: 2px;
  left: 2px;
  z-index: 3;
  padding: 0 3px;
  border-radius: 1px;
  font-family: var(--font-brush);
  font-size: 0.58rem;
  line-height: 1.35;
  color: #f7e9d0;
  background: linear-gradient(158deg, #a8322b, #86201b);
  box-shadow: inset 0 0 0 1px rgba(247, 233, 208, 0.34);
  animation: revealNewPop 0.5s ease-out;
}
@keyframes revealNewPop {
  0% { opacity: 0; transform: translateY(3px) scale(0.6); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}

/* 抽奖进行时，两个金钮的位置换成进度条 */
.reveal-bar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.65rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.4);
  border-left: 2px solid var(--crimson);
  background: rgba(28, 24, 20, 0.9);
  color: var(--paper-dim);
  font-size: 0.74rem;
  cursor: pointer;
  user-select: none;
}
.reveal-bar__orb {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--crimson-2);
  animation: revealOrb 1s ease-in-out infinite;
}
@keyframes revealOrb {
  0%, 100% { opacity: 0.4; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1); }
}
.reveal-bar__text b { color: var(--gold-2); font-weight: 700; }
.reveal-bar__skip {
  margin-left: auto;
  color: var(--paper-mute);
  font-size: 0.68rem;
}

/* 还没连成的线：墨底 + 半透明图标，看得出是什么道具但不抢眼 */
.bonus {
  position: relative;
  aspect-ratio: 1 / 1;
  display: grid;
  place-items: center;
  border-radius: 1px;
  border: 1px solid rgba(166, 124, 78, 0.26);
  background: linear-gradient(180deg, rgba(58, 50, 42, 0.9), rgba(32, 27, 22, 0.95));
  transition: 0.2s;
}
.bonus .item-card__icon {
  opacity: 0.7;
  filter: saturate(0.85) brightness(1.15);
  transition: 0.2s;
  /* 7 列阵盘在手机上格子很小：图标跟着格子缩，别撑破边框 */
  width: min(20px, 62%) !important;
  height: auto !important;
  aspect-ratio: 1 / 1;
}
/* 连成后翻成浅宣纸底，一眼看出这条线已经拿下 */
.bonus.is-claimed {
  border-color: rgba(166, 124, 78, 0.7);
  background: linear-gradient(180deg, #e8ddc2, #d3c4a2);
}
.bonus.is-claimed .item-card__icon {
  opacity: 1;
  filter: none;
}
.bonus__qty {
  position: absolute;
  right: 1px;
  bottom: 0;
  font-size: 0.5rem;
  line-height: 1;
  color: var(--paper);
  text-shadow: 0 1px 2px #000;
}
.bonus.is-claimed .bonus__qty {
  color: #5c4620;
  text-shadow: none;
}
/* 右下角并放主/副两条斜线 */
.bonus--diag {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1px;
}
/* 对角格里的皮肤：圆形裁切会把横版立绘裁成一团，改成方形并提亮，一眼能认出是皮肤 */
.bonus--skin:not(.is-claimed) {
  box-shadow: inset 0 0 0 1px rgba(166, 124, 78, 0.5);
}
.bonus--skin .item-card__icon {
  border-radius: 1px;
  opacity: 1;
  filter: saturate(1.1) brightness(1.12);
}
.bonus--skin.is-claimed .item-card__icon {
  filter: none;
}

.pull-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.45rem; }
/* 状态提示条：用墨痕分割 */
.pull-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  margin: -0.15rem 0 0;
  padding-top: 0.3rem;
  font-size: 0.64rem;
  color: var(--paper-mute);
  border-top: 1px solid transparent;
  border-image: linear-gradient(90deg, transparent, rgba(166, 124, 78, 0.42), transparent) 1;
}
.pull-hint b { color: var(--gold-2); font-variant-numeric: tabular-nums; }
.pull-hint__buy {
  padding: 0.1rem 0.5rem;
  border-radius: 2px;
  font-size: 0.62rem;
  letter-spacing: 0.04em;
  color: var(--paper);
  background: rgba(166, 124, 78, 0.18);
  border: 1px solid rgba(166, 124, 78, 0.42);
}
.pull-hint__buy:hover { background: rgba(166, 124, 78, 0.3); }
/* 回忆按钮＝朱砂战旗 */
.pull-btn {
  position: relative;
  display: grid;
  gap: 1px;
  padding: 0.42rem 0.3rem 0.46rem;
  border-radius: 2px;
  border: 1px solid rgba(247, 233, 208, 0.28);
  background: linear-gradient(178deg, #a8322b 0%, #9e2b25 55%, #7d1d19 100%);
  overflow: hidden;
  transition: filter 0.14s, transform 0.14s;
}
.pull-btn::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--tex-drybrush);
  background-repeat: repeat-x;
  background-size: 240px 16px;
  opacity: 0;
  transform: translateX(-70%);
  pointer-events: none;
}
.pull-btn:not(:disabled):hover { filter: brightness(1.06); }
.pull-btn:not(:disabled):hover::after { animation: brushSweep 0.34s ease-out both; }
.pull-btn:not(:disabled):active { transform: translateY(1px); }
.pull-btn:disabled { opacity: 0.4; filter: grayscale(0.4); }
.pull-btn--ten {
  background: linear-gradient(178deg, #b23a31 0%, #a32e27 55%, #85211c 100%);
}
.pull-btn__cost {
  font-size: 0.58rem;
  letter-spacing: 0.02em;
  color: rgba(253, 242, 221, 0.72);
}
.pull-btn__label {
  font-family: var(--font-sans);
  font-size: 0.84rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #fdf2dd;
}
.board-stage__foot {
  display: flex;
  justify-content: space-between;
  gap: 0.4rem;
  font-size: 0.64rem;
  color: var(--paper-mute);
}
.done-tag { color: #a3b092; }

/* ================= 本次获得 ================= */
.gain-bar {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin-top: 0.7rem;
  padding: 0.5rem 0.7rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.22);
  background: linear-gradient(180deg, rgba(45, 39, 32, 0.92), rgba(22, 19, 16, 0.95));
  overflow: hidden;
}
.gain-bar__label { flex: none; font-size: 0.68rem; letter-spacing: 0.12em; color: var(--paper-dim); }
.gain-bar__items { display: flex; gap: 0.5rem; overflow-x: auto; padding-bottom: 2px; }
.gain-item { flex: none; display: grid; justify-items: center; gap: 1px; width: 52px; }
.gain-item__art {
  position: relative;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 1px;
  border: 1px solid rgba(166, 124, 78, 0.3);
  background: rgba(18, 15, 13, 0.5);
}
.gain-item__qty {
  position: absolute;
  right: 1px;
  bottom: 0;
  font-size: 0.56rem;
  color: var(--paper);
  text-shadow: 0 1px 2px #000;
}
.gain-item__name {
  width: 100%;
  font-size: 0.56rem;
  text-align: center;
  color: var(--paper-mute);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ================= 详情 ================= */
.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 0.75rem;
  margin-top: 0.75rem;
  align-items: start;
}
.detail-side { display: grid; gap: 0.75rem; }

.line-groups { display: grid; gap: 0.55rem; }
.line-group__title {
  margin: 0 0 0.25rem;
  font-family: var(--font-display);
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  color: var(--paper-mute);
}
.line-list { display: grid; gap: 0.22rem; }
.line-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.26rem 0.4rem;
  border-radius: 1px;
  border: 1px solid rgba(166, 124, 78, 0.12);
  border-left: 2px solid transparent;
  background: rgba(236, 226, 202, 0.02);
  font-size: 0.72rem;
}
.line-row.is-claimed {
  border-color: rgba(166, 124, 78, 0.34);
  border-left-color: rgba(158, 43, 37, 0.75);
  background: rgba(166, 124, 78, 0.06);
}
.line-row__main { flex: 1; min-width: 0; display: grid; gap: 1px; }
.line-row__name { color: var(--paper); }
.line-row__cells { font-size: 0.6rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.line-row__qty { color: var(--paper-dim); font-variant-numeric: tabular-nums; }
.line-row__state { flex: none; font-size: 0.6rem; color: var(--paper-mute); letter-spacing: 0.06em; }
.line-row.is-claimed .line-row__state { color: #a3b092; }

.final-mini {
  display: flex;
  gap: 0.6rem;
  align-items: center;
}
.final-mini__art {
  position: relative;
  flex: none;
  width: 78px;
  height: 78px;
  border-radius: 2px;
  overflow: hidden;
  border: 1px solid rgba(166, 124, 78, 0.36);
  background: rgba(18, 15, 13, 0.6);
  display: grid;
  place-items: center;
}
.final-mini__art img { width: 100%; height: 100%; object-fit: cover; }
.final-mini__glyph { font-family: var(--font-brush); color: var(--paper-dim); }
.final-mini__seal {
  position: absolute;
  right: 2px;
  bottom: 2px;
  padding: 0 4px;
  border-radius: 1px;
  font-family: var(--font-brush);
  font-size: 0.6rem;
  color: #f7e9d0;
  background: linear-gradient(158deg, #a8322b, #86201b);
  box-shadow: inset 0 0 0 1px rgba(247, 233, 208, 0.32);
  transform: rotate(-3deg);
}
.final-mini__body { min-width: 0; flex: 1; }
.final-mini__eyebrow {
  margin: 0;
  font-size: 0.6rem;
  letter-spacing: 0.14em;
  color: var(--paper-mute);
}
.final-mini__body h3 {
  margin: 0.1rem 0 0.2rem;
  font-family: var(--font-brush);
  font-weight: 400;
  font-size: 1rem;
  letter-spacing: 0.04em;
  color: var(--paper);
}
.final-mini__body p { margin: 0; font-size: 0.66rem; line-height: 1.5; }
/* 进度条＝赭石金墨痕 */
.final-mini__track {
  margin-top: 0.35rem;
  height: 3px;
  border-radius: 0;
  background: rgba(236, 226, 202, 0.08);
  overflow: hidden;
}
.final-mini__fill {
  height: 100%;
  background: linear-gradient(90deg, rgba(166, 124, 78, 0.5), var(--gold));
  transition: width 0.45s;
}

.rate-table { width: 100%; border-collapse: collapse; font-size: 0.7rem; font-family: var(--font-num); }
.rate-table th {
  text-align: left;
  padding: 0.2rem 0.3rem;
  font-weight: 400;
  color: var(--paper-mute);
  border-bottom: 1px solid rgba(166, 124, 78, 0.2);
}
.rate-table td {
  padding: 0.22rem 0.3rem;
  color: var(--paper-dim);
  border-bottom: 1px solid rgba(166, 124, 78, 0.1);
}
.rate-note { margin: 0.4rem 0 0; font-size: 0.62rem; line-height: 1.5; }

/* 概率：单列清单 + 合计行 */
.prob-list { display: grid; }
.prob-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.28rem 0.3rem;
  font-size: 0.74rem;
  border-bottom: 1px solid rgba(166, 124, 78, 0.1);
}
.prob-row:nth-child(odd) { background: rgba(236, 226, 202, 0.014); }
.prob-row__name {
  display: flex;
  align-items: baseline;
  gap: 0.15rem;
  color: var(--paper);
}
.prob-row__name i { font-style: normal; font-size: 0.82em; color: var(--paper-mute); }
.prob-row__pct {
  margin-left: auto;
  color: var(--paper);
  font-family: var(--font-num);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.prob-row--sum {
  margin-top: 0.1rem;
  border-bottom: none;
  border-top: 1px solid rgba(166, 124, 78, 0.3);
  background: rgba(166, 124, 78, 0.06);
}
.prob-row--sum .prob-row__name,
.prob-row--sum .prob-row__pct { color: var(--gold-2); }
.prob-row__sum {
  width: 24px;
  text-align: center;
  font-size: 0.9rem;
  color: var(--paper-dim);
}


.rules { margin: 0; padding-left: 1rem; font-size: 0.7rem; line-height: 1.7; color: var(--paper-mute); }
.rules__src { margin: 0.4rem 0 0; font-size: 0.62rem; }

/* ================= 补给弹层 ================= */
.supply-mask { z-index: 96; }
/* 游戏内「迷迭珠不足」对话框：旧羊皮纸 + 墨/朱双钮 */
.supply-dialog {
  width: min(400px, 92vw);
  padding: 1.5rem 1.4rem 0.9rem;
  border-radius: 2px;
  border: 1px solid #6b563a;
  background:
    radial-gradient(120% 90% at 50% 0%, rgba(255, 255, 255, 0.22), transparent 60%),
    linear-gradient(180deg, #e8dcbe 0%, #d9c9a4 55%, #cbb994 100%);
  box-shadow:
    0 20px 56px rgba(0, 0, 0, 0.62),
    inset 0 0 0 2px rgba(255, 255, 255, 0.38),
    inset 0 0 26px rgba(120, 92, 52, 0.28);
  color: #3a2c18;
}
.supply-dialog__line {
  margin: 0 0 0.55rem;
  font-family: var(--font-brush);
  font-size: 1.1rem;
  line-height: 1.7;
  letter-spacing: 0.03em;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.45);
}
.supply-dialog__line .num {
  color: #9e2b25;
  font-weight: 700;
  font-family: var(--font-num);
  font-variant-numeric: tabular-nums;
}
.supply-dialog__acts {
  display: flex;
  justify-content: space-between;
  gap: 1.2rem;
  margin: 1.35rem 0 0.75rem;
}
.supply-btn {
  flex: 1;
  padding: 0.46rem 0.8rem;
  border-radius: 2px;
  border: 1px solid #3f3120;
  font-family: var(--font-brush);
  font-size: 1rem;
  letter-spacing: 0.14em;
  color: #f4ecd4;
  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.55);
  transition: 0.15s;
}
.supply-btn--cancel {
  background: linear-gradient(180deg, #4a423a, #2d2720);
}
.supply-btn--ok {
  background: linear-gradient(180deg, #ad3830, #8a211c);
  border-color: #6d1a16;
  box-shadow: inset 0 1px 0 rgba(255, 236, 210, 0.22);
}
.supply-btn:hover:not(:disabled) { filter: brightness(1.1); }
.supply-btn:active:not(:disabled) { transform: translateY(1px); }
.supply-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.supply-dialog__mute {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
  color: #5b4a30;
  cursor: pointer;
  user-select: none;
}
.supply-dialog__mute input {
  width: 14px;
  height: 14px;
  accent-color: #9e2b25;
  cursor: pointer;
}
.supply-dialog__warn {
  margin: 0.55rem 0 0;
  font-size: 0.7rem;
  color: #a3361b;
}
.supply-dialog__warn a { color: #7c4a12; text-decoration: underline; }

/* ================= 响应式 ================= */
@media (max-width: 1320px) {
  /* 留白变窄：两侧一起收，别贴到内容上 */
  .if--edge-l { width: clamp(44px, 6.4vw, 82px); opacity: 0.62; }
  .if--edge-r { width: clamp(74px, 9vw, 120px); opacity: 0.6; }
  .if--flag { width: 42px; height: 132px; }
}
@media (max-width: 1280px) {
  /* shell 1180 + 边距之后几乎没有余白，右侧整组收掉 */
  .if--edge-r, .if--flag, .if--dust, .if--seal-b { display: none; }
  .if--edge-l { width: 42px; opacity: 0.24; }
  .if--fibre-l { display: none; }
  .if--floor { height: 120px; opacity: 0.68; }
  .if--seal-a { opacity: 0.16; }
}
@media (max-width: 1080px) {
  .stage { grid-template-columns: 110px minmax(0, 1fr) 306px; }
}
@media (max-width: 940px) {
  .stage { grid-template-columns: minmax(0, 1fr); }
  .period-list {
    flex-direction: row;
    max-height: none;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 4px;
  }
  .period-item { flex: 0 0 auto; }
  .hero-stage { min-height: 340px; }
  .detail-grid { grid-template-columns: minmax(0, 1fr); }
  /* 单栏后两侧无留白，气氛层只留底部沉积 */
  .if--edge-l, .if--seal-a { display: none; }
  .if--floor { height: 100px; opacity: 0.6; }
}
@media (max-width: 620px) {
  .corridor-page { padding-top: 0.6rem; }
  .topbar { padding: 0.45rem 0.55rem; gap: 0.5rem; }
  .topbar__title { font-size: 0.9rem; letter-spacing: 0.1em; }
  .res-chip { font-size: 0.7rem; padding: 0.16rem 0.4rem; }
  .box-card__body { flex-wrap: wrap; gap: 0.5rem; padding: 0.5rem; }
  .box-card__thumb { width: 54px; height: 54px; }
  .box-card__title { font-size: 0.92rem; }
  .box-card__intro { font-size: 0.68rem; }
  .box-card__meta { max-width: none; width: 100%; justify-content: flex-start; }
  .hero-stage { min-height: 280px; }
  .hero-stage__caption { bottom: 1.7rem; }
  .board-stage { padding: 0.55rem; }
  .cell { font-size: 0.66rem; }
  .line-strip { width: 32px; }
  .pull-btn__label { font-size: 0.78rem; }
}
</style>
