<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import ItemGlyph from '../components/ItemGlyph.vue'
import ResultModal from '../components/ResultModal.vue'
import { mediaUrl, focusPosition } from '../assets/media.js'
import { useToast } from '../composables/useToast'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const { success: toastSuccess, error: toastError } = useToast()

const data = ref(null)
const loading = ref(true)
const pulling = ref(false)
const buying = ref(false)
const result = ref(null)
const modalOpen = ref(false)
const breaking = ref(new Set())

// 棋盘：照官方天宫宝库的排布 —— 5 列 × 3 行。
//   第 1 行：4 个普通格 + 皮肤大奖（右上）
//   第 2 行：左右各 1 个普通格，中间 3 列并给幸运值面板
//   第 3 行：4 个普通格 + 武将大奖（右下）
// 普通格按道具 key 落座，key 对应 backend/app/data/palace.json 的 grid 定义。
const SEATS = [
  { key: 'feather', row: 1, col: 1 }, // 雁翎
  { key: 'basket', row: 1, col: 2 }, // 菜篮子
  { key: 'silver', row: 1, col: 3 }, // 银币
  { key: 'luck_card_2', row: 1, col: 4 }, // 手气卡
  { grand: 'skin', row: 1, col: 5 }, // 皮肤（右上）
  { key: 'swap_card_2', row: 2, col: 1 }, // 换将卡
  { key: 'bean', row: 2, col: 5 }, // 欢乐豆
  { key: 'soul_1000', row: 3, col: 1 }, // 将魂
  { key: 'pill_1', row: 3, col: 2 }, // 进阶丹
  { key: 'armor_1', row: 3, col: 3 }, // 雁翎甲
  { key: 'token_1', row: 3, col: 4 }, // 招募令
  { grand: 'hero', row: 3, col: 5 }, // 武将（右下）
]

// 大奖格里的白色剪影（皮肤 = 连衣裙，武将 = 头盔），对应官方金牌上的浮雕图标
const GRAND_ART = {
  skin: 'M27 7 37 7 39.5 15.5 34.5 21 45.5 57 18.5 57 29.5 21 24.5 15.5Z',
  hero: 'M32 3.5 36 10 28 10Z M32 8.5C22.5 8.5 16.5 16.5 16.5 26.5L16.5 33 47.5 33 47.5 26.5C47.5 16.5 41.5 8.5 32 8.5Z M13.5 33.5 50.5 33.5 46.5 40.5 17.5 40.5Z M17.5 41 23.5 41 22.5 50.5 14.5 48.5Z M40.5 41 46.5 41 49.5 48.5 41.5 50.5Z',
}

const cells = computed(() => {
  if (!data.value) return []
  const entries = data.value.entries
  const normals = entries.filter((e) => !e.grand)
  const byKey = new Map(normals.map((e) => [e.key, e]))
  const used = new Set()

  const placed = SEATS.map((seat) => {
    let entry = null
    if (seat.grand) {
      entry = entries.find((e) => e.grand === seat.grand) || null
    } else if (byKey.has(seat.key)) {
      entry = byKey.get(seat.key)
      used.add(entry.key)
    }
    return { seat, entry }
  })

  // 兜底：奖池换了道具（key 改名 / 增删）时，没落座的格子按原顺序补进空位，
  // 保证棋盘永远 12 格，不会因为一个 key 对不上就少画一格。
  const spare = normals.filter((e) => !used.has(e.key))
  for (const slot of placed) {
    if (!slot.entry && !slot.seat.grand && spare.length) {
      slot.entry = spare.shift()
      used.add(slot.entry.key)
    }
  }

  return placed
    .filter((s) => s.entry)
    .map(({ seat, entry }) => ({ ...entry, row: seat.row, col: seat.col }))
})

const periods = computed(() => data.value?.periods || [])
const activePeriod = computed(() => data.value?.id || '')
const isCurrent = computed(() => !!data.value?.is_current)

const featured = computed(() => data.value?.featured || '')
const featuredArt = computed(() => (featured.value ? mediaUrl(featured.value, 'hero') : ''))
const featuredFocus = computed(() => focusPosition(featured.value ? `hero:${featured.value}` : ''))

const luckPct = computed(() =>
  data.value ? Math.min(100, (data.value.luck / data.value.pity_limit) * 100) : 0,
)

const owned = computed(() => data.value?.owned_cost_item ?? 0)
// 天工石不够时不再把按钮置灰：点下去先弹「补给」弹层，买够自动接着抓
const canPull = () => !!data.value && !pulling.value && isCurrent.value
const yuanbao = computed(() => auth.yuanbao)
const canBuy = (n) =>
  !!data.value && !buying.value && yuanbao.value >= data.value.cost_price * n && isCurrent.value

// ---------------- 天工石补给弹层 ----------------
const supplyOpen = ref(false)
const pendingPull = ref(0) // 0 = 单纯补给；>0 = 买够后继续抓这么多次
const supplyNeed = computed(() => Math.max(0, pendingPull.value - owned.value))
const supplyTitle = computed(() => (pendingPull.value ? '天工石不足' : '补给天工石'))

function openSupply(count = 0) {
  pendingPull.value = count
  supplyOpen.value = true
}

function closeSupply() {
  supplyOpen.value = false
  pendingPull.value = 0
}

/** 弹层里补够了（或本来只是差一点）：直接接着抓 */
async function resumePull() {
  const n = pendingPull.value
  if (!n) return
  supplyOpen.value = false
  pendingPull.value = 0
  await pull(n)
}

const probText = (p) => {
  const n = Number(p)
  if (!n) return '0%'
  const s = n < 0.1 ? n.toFixed(3) : n.toFixed(2)
  return `${s.replace(/0+$/, '').replace(/\.$/, '')}%`
}

const artSrc = (name, kind) => {
  const key = `${kind}:${name}`
  if (breaking.value.has(key)) return ''
  return mediaUrl(name, kind)
}
const markBroken = (name, kind) => {
  const next = new Set(breaking.value)
  next.add(`${kind}:${name}`)
  breaking.value = next
}

async function load(period = '') {
  loading.value = !data.value
  try {
    data.value = await api.palace(period)
  } catch (err) {
    toastError(err.message)
  } finally {
    loading.value = false
  }
}

async function switchPeriod(id) {
  if (id === activePeriod.value || pulling.value) return
  await load(id)
}

async function buy(n) {
  if (!canBuy(n)) return
  buying.value = true
  try {
    const res = await api.buyItem('stone_ti', n)
    auth.setYuanbao(res.yuanbao)
    data.value.owned_cost_item = res.owned
    toastSuccess(`购入「${res.name}」× ${res.count}，花费 ${res.spent.toLocaleString('zh-CN')} 元宝`)

    // 买够了就把刚才点的那一次直接抓掉，不用再点一遍
    const wait = pendingPull.value
    if (wait && res.owned >= wait) {
      supplyOpen.value = false
      pendingPull.value = 0
      await pull(wait)
    }
  } catch (err) {
    toastError(err.message)
  } finally {
    buying.value = false
  }
}

async function pull(n) {
  if (pulling.value) return
  if (!isCurrent.value) {
    toastError('往期宝库只能回看奖池，抽取请在当期进行。')
    return
  }
  if (owned.value < n) {
    // 不够就直接把「补给」摆到面前，买完自动续抓
    openSupply(n)
    return
  }
  pulling.value = true
  modalOpen.value = false
  try {
    const [res] = await Promise.all([
      api.palacePull(n, data.value.id),
      new Promise((r) => setTimeout(r, 520)),
    ])
    data.value.luck = res.luck
    data.value.pulls = res.pulls
    data.value.jackpots = res.jackpots
    data.value.owned_cost_item = res.owned_cost_item
    data.value.grand_probability = res.grand_probability
    data.value.grand_owned = data.value.grand_owned || { hero: [], skin: [] }
    for (const hit of res.grand_hits) {
      // 抽到即拥有（重复大奖也说明已经有了）：同一件在十连里连中两次时，
      // 旧写法靠 results 里有没有「非重复」那条来判断，会把卡面漏标成未拥有。
      const list = data.value.grand_owned[hit.kind] || (data.value.grand_owned[hit.kind] = [])
      if (!list.includes(hit.name)) list.push(hit.name)
    }
    result.value = res
    modalOpen.value = true

    if (res.grand_hits.length) {
      const hit = res.grand_hits[0]
      toastSuccess(
        hit.duplicate
          ? `重复获得「${hit.name}」，返还 ${hit.refund} 颗天工石`
          : `天命所归！本期大奖「${hit.name}」已收入背包`,
      )
    }
  } catch (err) {
    toastError(err.message)
  } finally {
    pulling.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="shell palace-page">
    <!-- 两侧「墨框宝库」气氛层：固定贴视口、不参与布局、不挡点击。
         只补结构，奖励格与业务一律不动。 -->
    <div class="ink-field" aria-hidden="true">
      <!-- 左：旧录簿侧缘的一道竖向枯笔 -->
      <span class="if if--edge-l"></span>
      <!-- 左：册页目录式的极淡短墨痕 -->
      <span class="if if--ticks"></span>
      <!-- 底：横向墨沉积（先铺，右侧才不被压掉） -->
      <span class="if if--floor"></span>
      <!-- 右：卷轴式淡墨边 + 宣纸纤维 + 旧纸折痕 -->
      <span class="if if--edge-r"></span>
      <!-- 右上：一条克制的残旗 -->
      <span class="if if--flag"></span>
      <!-- 右：飞墨小点 -->
      <span class="if if--dust"></span>
      <span class="if if--seal if--seal-a">藏</span>
      <span class="if if--seal if--seal-b">鉴</span>
    </div>

    <div class="crumbs">
      <router-link to="/" class="crumb">大厅</router-link>
      <span class="crumb-sep">/</span>
      <span class="crumb crumb--current">天宫宝库</span>
    </div>

    <div v-if="loading" class="empty">正在开库门……</div>

    <template v-else-if="data">
      <!-- 期数切换 -->
      <div class="period-bar">
        <button
          v-for="p in periods"
          :key="p.id"
          class="period-chip"
          :class="{ 'is-active': p.id === activePeriod, 'is-current': p.current }"
          @click="switchPeriod(p.id)"
        >
          <b>{{ p.label }}</b>
          <i>{{ p.current ? '进行中' : '往期' }}</i>
        </button>
      </div>

      <!-- 顶部横幅：主推武将 + 货币栏 -->
      <section class="palace-banner">
        <div class="banner-art">
          <img
            v-if="featuredArt"
            :src="featuredArt"
            :alt="featured"
            :style="{ objectPosition: featuredFocus }"
            @error="markBroken(featured, 'hero')"
          />
          <div class="banner-nameplate">{{ featured }}</div>
        </div>
        <div class="banner-info">
          <h1 class="banner-title">
            天宫宝库
            <span class="banner-badge">{{ data.label }}</span>
            <i class="seal-stamp seal-stamp--sm" aria-hidden="true">宝</i>
          </h1>
          <p class="banner-dates">活动时间：{{ data.dates }}</p>
          <p class="banner-desc subtle">
            每抽 +1 幸运值，幸运值越高大奖概率越高，满 {{ data.pity_limit }} 抽必中大奖；重复中奖返还
            {{ data.repeat_refund }} 天工石。
          </p>
        </div>
        <div class="banner-currency">
          <div class="coin-chip">
            <ItemGlyph name="天工石" kind="item" rarity="epic" :size="22" />
            <b>{{ owned }}</b>
            <span>天工石</span>
          </div>
          <div class="coin-chip">
            <span class="yb">宝</span>
            <b>{{ yuanbao.toLocaleString('zh-CN') }}</b>
            <span>元宝</span>
          </div>
        </div>
      </section>

      <!-- 主体：棋盘 + 大奖架 -->
      <section class="palace-main">
        <div class="board-wrap">
          <div class="board">
            <div
              v-for="cell in cells"
              :key="cell.key"
              class="tile"
              :class="[
                `tier-${cell.tier}`,
                cell.grand ? `tile--grand tile--grand-${cell.grand}` : `r-${cell.rarity}`,
              ]"
              :style="{ gridArea: `${cell.row} / ${cell.col}` }"
              :title="`${cell.name} · ${probText(cell.probability)}`"
            >
              <template v-if="cell.grand">
                <svg class="tile__grand-art" viewBox="0 0 64 64" aria-hidden="true">
                  <path :d="GRAND_ART[cell.grand]" />
                </svg>
                <span class="tile__grand-label">{{ cell.grand === 'hero' ? '武将' : '皮肤' }}</span>
              </template>
              <template v-else>
                <span v-if="cell.qty > 1" class="tile__qty">×{{ cell.qty }}</span>
                <ItemGlyph
                  class="tile__art"
                  :name="cell.name"
                  :kind="cell.kind"
                  :rarity="cell.rarity"
                  :size="64"
                />
                <span class="tile__name">{{ cell.name }}</span>
              </template>
            </div>

            <div class="luck-center">
              <div class="luck-num">幸运值 <b>{{ data.luck }}</b></div>
              <div class="luck-hint">满 {{ data.pity_limit }} 次必中大奖</div>
              <div class="luck-track">
                <div class="luck-fill" :style="{ width: `${luckPct}%` }" />
              </div>
              <div class="luck-prob">
                还剩 <b>{{ Math.max(0, data.pity_limit - data.luck) }}</b> 次 · 当前大奖率
                <b class="gold">{{ probText(data.grand_probability) }}</b>
              </div>
            </div>
          </div>

          <!-- 网格边缘的极淡墨气：下方案面一道斜笔、右上格角一片淡晕 -->
          <div class="board-ink" aria-hidden="true">
            <span class="bi bi--blade"></span>
            <span class="bi bi--wash"></span>
          </div>

          <div class="board-actions">
            <button class="draw-btn" :disabled="!canPull(1)" @click="pull(1)">
              <span class="draw-btn__cost">消耗 <ItemGlyph name="天工石" kind="item" rarity="epic" :size="18" /> ×1</span>
              <b>抓 1 次</b>
            </button>
            <button class="draw-btn draw-btn--ten" :disabled="!canPull(10)" @click="pull(10)">
              <span class="draw-btn__cost">消耗 <ItemGlyph name="天工石" kind="item" rarity="epic" :size="18" /> ×10</span>
              <b>抓 10 次</b>
            </button>
            <div class="buy-row">
              <span class="buy-row__owned">
                <ItemGlyph name="天工石" kind="item" rarity="epic" :size="16" />
                现有 <b>{{ owned }}</b> 颗
              </span>
              <button class="buy-row__link" :disabled="!isCurrent" @click="openSupply(0)">补给 +</button>
              <span class="subtle">{{ data.cost_price }} 元宝 / 颗</span>
            </div>
          </div>

          <p v-if="!isCurrent" class="past-note">
            这是往期宝库（{{ data.label }} · {{ data.dates }}），仅可回看奖池与大奖；抽取请回到当期。
          </p>
          <div class="stats-row subtle">
            本期累计 <b>{{ data.pulls }}</b> 抽 · 已中大奖 <b>{{ data.jackpots }}</b> 次 ·
            普通 85% / 精品 14.7% / 稀有 0.3%
          </div>
        </div>

        <!-- 右侧大奖架 -->
        <aside class="shelf-col">
          <div
            v-for="shelf in [
              { key: 'hero', label: '武将大奖', cls: 'shelf--blue' },
              { key: 'skin', label: '皮肤大奖', cls: 'shelf--red' },
            ]"
            :key="shelf.key"
            class="shelf"
            :class="shelf.cls"
          >
            <div class="shelf__ribbon">{{ shelf.label }} · 3 选 1</div>
            <div class="shelf__cards">
              <div
                v-for="name in data.grand_prizes[shelf.key]"
                :key="name"
                class="prize-card"
                :class="{ 'is-owned': (data.grand_owned[shelf.key] || []).includes(name) }"
              >
                <img
                  v-if="artSrc(name, shelf.key)"
                  :src="artSrc(name, shelf.key)"
                  :alt="name"
                  :style="{ objectPosition: focusPosition(shelf.key) }"
                  loading="lazy"
                  @error="markBroken(name, shelf.key)"
                />
                <span v-else class="prize-card__glyph">{{ name.slice(-2) }}</span>
                <span class="prize-card__tag">史诗</span>
                <span v-if="(data.grand_owned[shelf.key] || []).includes(name)" class="prize-card__owned">已拥有</span>
                <span class="prize-card__name">{{ name }}</span>
              </div>
            </div>
          </div>

          <section class="panel panel--pad rules-panel">
            <div class="panel__head">
              <h3>规则 <i class="seal-stamp seal-stamp--xs" aria-hidden="true">规</i></h3>
            </div>
            <ol class="rules">
              <li v-for="(rule, i) in data.rules" :key="i">{{ rule }}</li>
            </ol>
            <a
              v-if="data.rules_url"
              class="rules-src"
              :href="data.rules_url"
              target="_blank"
              rel="noopener noreferrer"
            >官方概率公示 ↗</a>
          </section>
        </aside>
      </section>

      <p class="src-note subtle">
        各期大奖与奖池依据官网活动公告与概率公示整理（第 1 期 ～ {{ periods.length ? periods[periods.length - 1].label : '当期' }}，
        共 {{ periods.length }} 期），仅作模拟演示。
      </p>
    </template>

    <ResultModal
      :open="modalOpen"
      :data="result"
      :title="data ? `${data.name} · ${data.label}` : '天宫宝库'"
      :loading="pulling"
      :again-label="`再抓 ${result?.count || 1} 次`"
      @close="modalOpen = false"
      @again="pull(result?.count || 1)"
    />

    <!-- ================= 天工石补给 ================= -->
    <div v-if="supplyOpen && data" class="modal-mask supply-mask" @click.self="closeSupply">
      <div class="modal supply-modal">
        <div class="modal__head">
          <h3 class="modal__title">{{ supplyTitle }}</h3>
          <button class="modal__close" @click="closeSupply">×</button>
        </div>

        <p class="supply-modal__lead">
          <template v-if="pendingPull && supplyNeed">
            本次抓取需要 <b>{{ pendingPull }}</b> 颗天工石，当前只有 <b>{{ owned }}</b> 颗，
            <span class="nw">还差 <b class="gold">{{ supplyNeed }}</b> 颗</span>。
          </template>
          <template v-else-if="pendingPull">天工石已经够了，点下面的按钮继续抓取。</template>
          <template v-else>
            天工石 {{ data.cost_price }} 元宝 / 颗，买几颗都行，随时可用来抓取。
          </template>
        </p>

        <div class="supply-modal__row">
          <span class="supply-modal__res">
            <ItemGlyph name="天工石" kind="item" rarity="epic" :size="18" />
            <b>{{ owned }}</b>
          </span>
          <span class="supply-modal__res">
            <i class="res-chip__coin">¥</i>
            <b>{{ auth.yuanbao.toLocaleString('zh-CN') }}</b>
          </span>
        </div>

        <div class="supply-modal__opts">
          <button
            v-for="n in [1, 10, 50]"
            :key="n"
            class="supply-opt"
            :disabled="!canBuy(n) || buying"
            @click="buy(n)"
          >
            <span class="supply-opt__qty">买 {{ n }} 颗</span>
            <span class="supply-opt__cost">{{ (data.cost_price * n).toLocaleString('zh-CN') }} 元宝</span>
          </button>
        </div>

        <p v-if="auth.yuanbao < data.cost_price" class="supply-modal__warn">
          元宝不足，可先去 <router-link to="/shop">商店</router-link> 充点元宝。
        </p>

        <div class="modal__foot">
          <button
            v-if="pendingPull && supplyNeed"
            class="btn btn-gold"
            :disabled="!canBuy(supplyNeed) || buying"
            @click="buy(supplyNeed)"
          >
            补给 {{ supplyNeed }} 颗 · {{ (supplyNeed * data.cost_price).toLocaleString('zh-CN') }} 元宝
          </button>
          <button v-else-if="pendingPull" class="btn btn-gold" :disabled="pulling" @click="resumePull">
            继续抓取 {{ pendingPull }} 次
          </button>
          <button class="btn btn-ghost" @click="closeSupply">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.palace-page { padding-top: 1.8rem; }

.crumbs { display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; margin-bottom: 1rem; }
.crumb { color: var(--paper-mute); }
.crumb:hover { color: var(--gold); }
.crumb--current { color: var(--paper-dim); }
.crumb-sep { color: #4d453a; }

/* ================= 两侧气氛层：墨框宝库（藏录边 · 卷轴边） ================= */
/* 固定贴视口、z-index -1，压在内容之下，只在 shell 两侧的留白里显形 */
.ink-field {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  overflow: hidden;
}
.if { position: absolute; display: block; pointer-events: none; }

/* 左：旧录簿侧缘——从顶到底的一道竖向枯笔，粗细断续，左缘压重 */
.if--edge-l {
  left: 0;
  top: 0;
  bottom: 0;
  width: clamp(64px, 8.4vw, 122px);
  background-image:
    linear-gradient(
      180deg,
      transparent 0%,
      rgba(217, 198, 164, 0.12) 5%,
      rgba(217, 198, 164, 0.085) 46%,
      rgba(217, 198, 164, 0.045) 78%,
      transparent 97%
    ),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='720' viewBox='0 0 120 720' preserveAspectRatio='none'%3E%3Cdefs%3E%3ClinearGradient id='pg' x1='0' y1='0' x2='1' y2='0'%3E%3Cstop offset='0' stop-color='%23000000' stop-opacity='.42'/%3E%3Cstop offset='.38' stop-color='%23000000' stop-opacity='.16'/%3E%3Cstop offset='1' stop-color='%23000000' stop-opacity='0'/%3E%3C/linearGradient%3E%3Cfilter id='pf' x='-20%25' y='-3%25' width='140%25' height='106%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.06 0.012' numOctaves='4' seed='41' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='6' xChannelSelector='R' yChannelSelector='G'/%3E%3CfeGaussianBlur stdDeviation='.4'/%3E%3C/filter%3E%3C/defs%3E%3Crect width='120' height='720' fill='url(%23pg)'/%3E%3Cg filter='url(%23pf)' fill='%23d9c6a4'%3E%3Crect x='2' y='24' width='5.6' height='152' opacity='.16'/%3E%3Crect x='10' y='92' width='2.4' height='128' opacity='.085'/%3E%3Crect x='13' y='170' width='1.6' height='96' opacity='.05'/%3E%3Crect x='2.6' y='186' width='7' height='94' opacity='.14'/%3E%3Crect x='17' y='244' width='2.8' height='140' opacity='.06'/%3E%3Crect x='23' y='300' width='1.8' height='86' opacity='.04'/%3E%3Crect x='2' y='310' width='4.6' height='198' opacity='.12'/%3E%3Crect x='12' y='366' width='2.2' height='120' opacity='.06'/%3E%3Crect x='2.4' y='500' width='6.2' height='76' opacity='.135'/%3E%3Crect x='16' y='540' width='2.4' height='98' opacity='.05'/%3E%3Crect x='2' y='590' width='4.2' height='110' opacity='.11'/%3E%3Crect x='26' y='624' width='1.8' height='64' opacity='.045'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 1.6px 100%, 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.8;
  -webkit-mask-image: linear-gradient(90deg, #000 0 26%, rgba(0, 0, 0, 0.55) 62%, transparent 100%);
  mask-image: linear-gradient(90deg, #000 0 26%, rgba(0, 0, 0, 0.55) 62%, transparent 100%);
}

/* 左：册页目录式的极淡短墨痕——长短不一的横笔，只在边距里 */
.if--ticks {
  left: 0;
  top: 14vh;
  height: 56vh;
  width: clamp(46px, 6vw, 92px);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='92' height='460' viewBox='0 0 92 460' preserveAspectRatio='none'%3E%3Cdefs%3E%3Cfilter id='tf' x='-12%25' y='-30%25' width='124%25' height='160%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.03 0.11' numOctaves='3' seed='11' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='2.4' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23tf)' fill='%23d9c6a4'%3E%3Crect x='3' y='16' width='46' height='1.6' opacity='.1'/%3E%3Crect x='3' y='74' width='28' height='1.4' opacity='.06'/%3E%3Crect x='3' y='128' width='58' height='1.6' opacity='.09'/%3E%3Crect x='3' y='186' width='34' height='1.4' opacity='.055'/%3E%3Crect x='3' y='242' width='64' height='1.7' opacity='.095'/%3E%3Crect x='3' y='298' width='24' height='1.4' opacity='.05'/%3E%3Crect x='3' y='352' width='52' height='1.6' opacity='.085'/%3E%3Crect x='3' y='410' width='38' height='1.5' opacity='.06'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.92;
  -webkit-mask-image: linear-gradient(90deg, #000 0 46%, rgba(0, 0, 0, 0.42) 78%, transparent 100%);
  mask-image: linear-gradient(90deg, #000 0 46%, rgba(0, 0, 0, 0.42) 78%, transparent 100%);
}

/* 底：横向墨沉积，下方略暗、上方渐隐，去掉底部空飘 */
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
  opacity: 0.8;
}
/* 远山之上再压一层暗，避免它被读成一条发亮的横带 */
.if--floor::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: linear-gradient(
    to top,
    rgba(8, 7, 5, 0.56) 0%,
    rgba(9, 8, 6, 0.24) 42%,
    transparent 76%
  );
}

/* 右：卷轴式墨边——竖向淡墨晕染 + 宣纸纤维 + 旧纸折痕 */
.if--edge-r {
  right: 0;
  top: 5vh;
  bottom: 2vh;
  width: clamp(104px, 13vw, 238px);
  background-image:
    linear-gradient(to left, rgba(217, 198, 164, 0.15) 0 1.6px, transparent 1.6px),
    radial-gradient(82% 34% at 82% 28%, rgba(198, 178, 142, 0.15), transparent 82%),
    radial-gradient(74% 44% at 92% 68%, rgba(166, 124, 78, 0.13), transparent 84%),
    linear-gradient(270deg, rgba(214, 196, 162, 0.07), rgba(12, 10, 8, 0.2) 58%, transparent 92%);
  background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.9;
  -webkit-mask-image: linear-gradient(270deg, #000 0 30%, rgba(0, 0, 0, 0.52) 66%, transparent 97%);
  mask-image: linear-gradient(270deg, #000 0 30%, rgba(0, 0, 0, 0.52) 66%, transparent 97%);
}

/* 极淡宣纸竖丝：窄条 + 小瓦片 repeat-y，避免整块噪声被拉伸 */
.if--edge-r::before {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 26%;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='120' viewBox='0 0 56 120'%3E%3Cdefs%3E%3Cfilter id='sf' x='-30%25' y='-10%25' width='160%25' height='120%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05 0.008' numOctaves='3' seed='9' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='5' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23sf)' fill='%23e6d6b6'%3E%3Crect x='40' y='0' width='.7' height='120' opacity='.05'/%3E%3Crect x='48' y='0' width='.9' height='120' opacity='.038'/%3E%3Crect x='33' y='0' width='.6' height='120' opacity='.03'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 56px 120px;
  background-repeat: repeat-y;
  opacity: 0.9;
  -webkit-mask-image: linear-gradient(270deg, #000, transparent 86%);
  mask-image: linear-gradient(270deg, #000, transparent 86%);
}

/* 旧纸折痕：断续的折线（不是一条贯穿的直线），只在纸面中段透出来 */
.if--edge-r::after {
  content: '';
  position: absolute;
  right: 28%;
  top: 6%;
  bottom: 10%;
  width: 26px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='26' height='520' viewBox='0 0 26 520' preserveAspectRatio='none'%3E%3Cdefs%3E%3Cfilter id='cf' x='-60%25' y='-6%25' width='220%25' height='112%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.12 0.03' numOctaves='3' seed='19' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='2.2' xChannelSelector='R' yChannelSelector='G'/%3E%3CfeGaussianBlur stdDeviation='.45'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23cf)'%3E%3Cg fill='%23050403'%3E%3Crect x='11' y='36' width='1.5' height='74' opacity='.3'/%3E%3Crect x='11.4' y='128' width='1.3' height='52' opacity='.22'/%3E%3Crect x='11' y='212' width='1.6' height='88' opacity='.28'/%3E%3Crect x='11.5' y='322' width='1.3' height='44' opacity='.2'/%3E%3Crect x='11' y='392' width='1.5' height='66' opacity='.26'/%3E%3C/g%3E%3Cg fill='%23e6d6b6'%3E%3Crect x='13.6' y='40' width='.9' height='66' opacity='.07'/%3E%3Crect x='14' y='216' width='.8' height='78' opacity='.06'/%3E%3Crect x='13.6' y='396' width='.9' height='56' opacity='.055'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.85;
  -webkit-mask-image: linear-gradient(180deg, transparent, #000 16%, #000 82%, transparent);
  mask-image: linear-gradient(180deg, transparent, #000 16%, #000 82%, transparent);
}

/* 右上：一条克制的残旗（按 1:1 像素画，缩放不会掉线） */
.if--flag {
  right: clamp(6px, 1.8vw, 34px);
  top: 7vh;
  width: clamp(38px, 4.2vw, 64px);
  height: clamp(116px, 18vh, 190px);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='232' viewBox='0 0 80 232' preserveAspectRatio='none'%3E%3Cg fill='none' stroke='%23e6d6b6' stroke-linecap='round' opacity='.16'%3E%3Cpath d='M62 232 L57 8' stroke-width='2.4'/%3E%3Cpath d='M57 24 C45 31 33 39 22 45 L31 52 L22 60 C34 64 46 71 57 77 Z' stroke-width='2'/%3E%3Cpath d='M57 152 C48 149 42 155 36 152' stroke-width='1.6'/%3E%3C/g%3E%3Cg fill='%23e6d6b6' opacity='.05'%3E%3Cpath d='M57 24 C45 31 33 39 22 45 L31 52 L22 60 C34 64 46 71 57 77 Z'/%3E%3C/g%3E%3C/svg%3E");
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

/* 两枚极小朱砂闲章：藏 / 鉴 */
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
.if--seal-a { left: clamp(5px, 1.2vw, 20px); top: 11vh; transform: rotate(-4.5deg); opacity: 0.3; }
.if--seal-b { right: clamp(5px, 1.3vw, 22px); bottom: 5.5vh; transform: rotate(3.5deg); opacity: 0.2; }

/* ================= 网格两侧的墨气：左下斜笔 · 右上淡晕 ================= */
/* 压在奖励格之上，但浓度只有 3–6%，只做“从墨色里展开”的感觉 */
.board-ink {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  overflow: hidden;
  border-radius: inherit;
}
.bi { position: absolute; display: block; }

.bi--blade {
  left: 1.5%;
  bottom: 3%;
  width: 30%;
  height: 15%;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='70' viewBox='0 0 300 70' preserveAspectRatio='none'%3E%3Cdefs%3E%3Cfilter id='pb' x='-8%25' y='-60%25' width='116%25' height='220%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.02 0.14' numOctaves='3' seed='5' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='3' xChannelSelector='R' yChannelSelector='G'/%3E%3CfeGaussianBlur stdDeviation='.35'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23pb)' fill='none' stroke-linecap='butt'%3E%3Cpath d='M2 62 C 74 52 150 40 236 24' stroke='%23d9c6a4' stroke-width='8' opacity='.115'/%3E%3Cpath d='M14 68 C 86 58 158 46 244 30' stroke='%23d9c6a4' stroke-width='3.4' opacity='.07'/%3E%3Cpath d='M40 44 C 108 36 174 26 246 12' stroke='%23e6d6b6' stroke-width='1.8' opacity='.06'/%3E%3Cpath d='M258 22 C 272 19 284 16 296 12' stroke='%23d9c6a4' stroke-width='4.4' opacity='.08'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.95;
  -webkit-mask-image: linear-gradient(96deg, transparent, #000 18%, #000 82%, transparent);
  mask-image: linear-gradient(96deg, transparent, #000 18%, #000 82%, transparent);
}

.bi--wash {
  right: 0;
  top: 0;
  width: 32%;
  height: 34%;
  background-image: radial-gradient(64% 64% at 92% 8%, rgba(140, 106, 66, 0.26), transparent 78%);
  opacity: 0.5;
  -webkit-mask-image: radial-gradient(80% 80% at 96% 4%, #000 18%, transparent 82%);
  mask-image: radial-gradient(80% 80% at 96% 4%, #000 18%, transparent 82%);
}

/* ---------------- 期数切换：横向小竹简 ---------------- */
.period-bar {
  display: flex;
  gap: 0.35rem;
  overflow-x: auto;
  padding-bottom: 0.5rem;
  margin-bottom: 0.9rem;
}
.period-chip {
  position: relative;
  flex: 0 0 auto;
  display: grid;
  gap: 1px;
  padding: 0.4rem 0.75rem;
  border-radius: 1px;
  border: 1px solid rgba(166, 124, 78, 0.2);
  background: linear-gradient(180deg, rgba(58, 50, 42, 0.5), rgba(33, 29, 25, 0.82));
  color: var(--paper-mute);
  cursor: pointer;
  transition: 0.18s;
  text-align: center;
}
.period-chip b { font-family: var(--font-sans); font-size: 0.78rem; color: var(--paper-dim); }
.period-chip i { font-style: normal; font-size: 0.6rem; letter-spacing: 0.1em; }
.period-chip:hover { border-color: rgba(166, 124, 78, 0.46); color: var(--paper-dim); }
.period-chip.is-active {
  border-color: rgba(166, 124, 78, 0.44);
  background: linear-gradient(180deg, rgba(70, 58, 44, 0.85), rgba(36, 31, 26, 0.9));
}
/* 激活态：底部一道枯笔 + 朱砂短线 */
.period-chip.is-active::after {
  content: '';
  position: absolute;
  left: 8%;
  right: 8%;
  bottom: -1px;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--crimson-2) 16%, var(--crimson) 62%, rgba(158, 43, 37, 0.2) 90%, transparent);
}
.period-chip.is-active b { color: var(--paper); }
.period-chip.is-current i { color: #a3b092; }

/* ---------------- 顶部横幅：暗战旗肌理，去蓝光 ---------------- */
.palace-banner {
  position: relative;
  display: grid;
  grid-template-columns: 220px 1fr auto;
  gap: 1.2rem;
  align-items: center;
  border-radius: 2px;
  overflow: hidden;
  border: 1px solid rgba(166, 124, 78, 0.28);
  background-color: var(--ink-700);
  background-image: linear-gradient(165deg, rgba(45, 39, 32, 0.97), rgba(20, 17, 14, 0.98));
}
/* 战旗布面：细竖纹 + 纤维 */
.palace-banner::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.5;
  background-image:
    repeating-linear-gradient(90deg, rgba(236, 226, 202, 0.028) 0 1px, transparent 1px 7px),
    var(--tex-fiber);
  background-size: auto, 180px 180px;
}
.banner-art {
  position: relative;
  align-self: stretch;
  min-height: 168px;
  overflow: hidden;
}
.banner-art img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.banner-art::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent 48%, rgba(22, 19, 16, 0.92));
}
.banner-nameplate {
  position: absolute;
  z-index: 2;
  left: 10px;
  top: 12px;
  padding: 3px 10px;
  border-radius: 1px;
  font-family: var(--font-brush);
  font-size: 1.05rem;
  letter-spacing: 0.08em;
  color: #f7e9d0;
  background: linear-gradient(158deg, #a8322b, #86201b);
  box-shadow: inset 0 0 0 1px rgba(247, 233, 208, 0.34);
  transform: rotate(-2deg);
}
.banner-info { position: relative; padding: 1rem 0; }
.banner-title {
  margin: 0;
  font-family: var(--font-brush);
  font-weight: 400;
  font-size: 1.7rem;
  letter-spacing: 0.14em;
  color: var(--paper);
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.banner-badge {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  padding: 2px 8px;
  border-radius: 1px;
  color: var(--paper-dim);
  background: rgba(166, 124, 78, 0.16);
  border: 1px solid rgba(166, 124, 78, 0.36);
}
.banner-dates { margin: 0.45rem 0 0; font-size: 0.82rem; color: var(--paper-mute); font-family: var(--font-num); }
.banner-desc { margin: 0.35rem 0 0; font-size: 0.74rem; max-width: 42em; line-height: 1.75; }
.banner-currency { position: relative; display: grid; gap: 0.4rem; padding: 1rem 1.2rem 1rem 0; }
/* 货币框＝竹简信息块 */
.coin-chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.28rem 0.7rem;
  border-radius: 2px;
  background: rgba(16, 13, 11, 0.5);
  border: 1px solid rgba(166, 124, 78, 0.24);
  font-size: 0.78rem;
  font-family: var(--font-num);
  color: var(--paper-mute);
}
/* 图标压成水墨色，别跳出来抢标题 */
.coin-chip :deep(.item-card__icon) {
  filter: sepia(0.4) saturate(0.62) brightness(0.94);
  border-radius: 2px !important;
}
.coin-chip b { color: var(--paper); font-variant-numeric: tabular-nums; }
.coin-chip .yb {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 0.64rem;
  color: #241a0e;
  background: radial-gradient(circle at 34% 30%, #d8bb8b, #a67c4e 68%, #7c5a34);
  border: 1px solid rgba(236, 226, 202, 0.26);
}

/* ---------------- 主体布局 ---------------- */
.palace-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 1.1rem;
  margin-top: 1.1rem;
  align-items: start;
}

/* 棋盘（木桌） */
/* 棋盘底：焦墨 + 极淡墨点，衬托浅宣纸方块 */
.board-wrap {
  position: relative;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.22);
  padding: 1.1rem 1.1rem 0.9rem;
  background-color: var(--ink-800);
  background-image: linear-gradient(170deg, rgba(45, 39, 32, 0.92), rgba(22, 19, 16, 0.96));
  box-shadow: inset 0 0 64px -34px rgba(0, 0, 0, 0.92);
}

/* 5 列 × 3 行：第 1 行 4 格 + 皮肤（右上），第 2 行左右各 1 格 + 中间 3 列幸运值，第 3 行 4 格 + 武将（右下） */
.board {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: clamp(6px, 1.6%, 14px);
  max-width: 880px;
  margin: 0 auto;
}

/* 道具格：浅米旧宣纸方块 + 极细枯墨描边 + 2px 圆角（不再是白色大卡片）
   4/5 略扁于 3/4，把省下的高度让给图标；图标占格宽 72% */
.tile {
  position: relative;
  aspect-ratio: 4 / 5;
  container-type: inline-size;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4.5% 3%;
  border-radius: 2px;
  border: 1px solid rgba(112, 96, 72, 0.42);
  background-color: #ece2c8;
  background-image: linear-gradient(178deg, #f0e7d2, #ded0af 78%, #cfbf9b);
  box-shadow: inset 0 0 0 1px rgba(255, 248, 232, 0.32);
  cursor: default;
  transition: transform 0.18s, border-color 0.18s;
}
/* 宣纸纤维 7% */
.tile::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.07;
  background-image: var(--tex-fiber);
  background-size: 160px 160px;
}
.tile:hover {
  transform: translateY(-2px);
  border-color: rgba(112, 96, 72, 0.7);
}
/* 道具图跟着格子宽度走：宽度用 %，字号用 cqi，手机 5 列也不会撑破边框 */
.tile :deep(.item-card__icon) {
  width: 72% !important;
  height: auto !important;
  aspect-ratio: 1 / 1;
  font-size: 27cqi !important;
  margin-bottom: 4%;
  border-radius: 2px !important;
  box-shadow: inset 0 0 0 1px rgba(255, 248, 232, 0.3);
}
.tile__qty {
  position: absolute;
  z-index: 2;
  top: 4%;
  right: 5%;
  padding: 0 4px;
  border-radius: 1px;
  background: rgba(38, 28, 16, 0.78);
  font-size: max(8px, 6.4cqi);
  font-weight: 700;
  line-height: 1.55;
  color: #f2e4c6;
}
.tile__name {
  position: relative;
  max-width: 100%;
  font-size: max(9px, 9cqi);
  line-height: 1.25;
  color: #4a3a22;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tile.tier-yellow { border-color: rgba(166, 124, 78, 0.62); }
.tile.tier-green { border-color: rgba(126, 138, 106, 0.7); }
.tile.tier-blue { border-color: rgba(140, 110, 74, 0.7); }
/* 稀有格：角落点一点朱砂印 */
.tile.tier-green::after,
.tile.tier-blue::after,
.tile.tier-red::after {
  content: '';
  position: absolute;
  right: 5px;
  bottom: 5px;
  width: 5px;
  height: 5px;
  border-radius: 1px;
  background: rgba(158, 43, 37, 0.82);
  transform: rotate(12deg);
}

/* 大奖格：赭石金牌底 + 白色剪影 + 底部字样（右上皮肤、右下武将） */
.tile--grand {
  justify-content: space-between;
  padding: 7% 5% 0;
  border-color: rgba(201, 164, 110, 0.72);
  background-image:
    radial-gradient(110% 80% at 66% 4%, #f6e8c8, transparent 64%),
    linear-gradient(166deg, #e3c894, #d4ac6e 58%, #b98d52);
}
.tile__grand-art {
  width: 74%;
  margin: 5% auto 0;
  fill: #fdf8ec;
  filter: drop-shadow(0 2px 3px rgba(96, 62, 20, 0.42));
}
.tile__grand-label {
  margin-bottom: 7%;
  font-family: var(--font-brush);
  font-size: max(11px, 12.5cqi);
  letter-spacing: 0.2em;
  text-indent: 0.2em;
  color: #fdf8ec;
  text-shadow: 0 1px 2px rgba(96, 56, 12, 0.8);
}

/* 中央幸运值：旧羊皮质感 + 赭石金墨痕进度 */
.luck-center {
  position: relative;
  grid-area: 2 / 2 / 3 / 5;
  container-type: inline-size;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: clamp(4px, 1.4cqi, 16px);
  padding: 4% 8%;
  border-radius: 2px;
  border: 1px solid rgba(112, 96, 72, 0.6);
  background-color: #d9c9a4;
  background-image:
    radial-gradient(120% 120% at 50% 0%, rgba(255, 250, 236, 0.34), transparent 62%),
    linear-gradient(178deg, #e2d4b4, #cdba93 72%, #bdaa83);
  box-shadow: inset 0 0 34px -16px rgba(104, 76, 40, 0.5);
  color: #4a3a22;
}
.luck-center::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.07;
  background-image: var(--tex-fiber);
  background-size: 160px 160px;
}
.luck-num {
  position: relative;
  font-family: var(--font-sans);
  font-size: clamp(0.72rem, 2.6cqi, 1.05rem);
  letter-spacing: 0.18em;
  color: #5d4a2c;
}
.luck-num b {
  font-family: var(--font-num);
  font-size: clamp(1.1rem, 4.6cqi, 2rem);
  letter-spacing: 0.04em;
  color: #8a211c;
  font-variant-numeric: tabular-nums;
}
.luck-track {
  position: relative;
  width: min(300px, 84%);
  height: clamp(4px, 0.9cqi, 7px);
  border-radius: 0;
  background: rgba(74, 58, 34, 0.24);
  overflow: hidden;
}
.luck-fill {
  height: 100%;
  border-radius: 0;
  background: linear-gradient(90deg, rgba(124, 90, 52, 0.55), var(--gold) 62%, var(--gold-2));
  transition: width 0.5s;
}
.luck-hint {
  position: relative;
  font-size: clamp(0.6rem, 2.1cqi, 0.85rem);
  color: #6b5a3c;
  letter-spacing: 0.06em;
}
.luck-prob {
  position: relative;
  font-size: clamp(0.58rem, 1.9cqi, 0.78rem);
  color: #7a6848;
  font-family: var(--font-num);
}
.luck-prob b { font-size: 1.08em; color: #8a211c; }

/* 抽奖按钮＝朱砂战旗 */
.board-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.9rem;
  margin-top: 1rem;
  flex-wrap: wrap;
}
.draw-btn {
  position: relative;
  display: grid;
  justify-items: center;
  gap: 0.12rem;
  min-width: 168px;
  padding: 0.5rem 1.1rem 0.55rem;
  border-radius: 2px;
  border: 1px solid rgba(247, 233, 208, 0.28);
  background: linear-gradient(178deg, #a8322b 0%, #9e2b25 55%, #7d1d19 100%);
  overflow: hidden;
  cursor: pointer;
  transition: filter 0.18s, transform 0.18s;
}
.draw-btn::after {
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
.draw-btn:hover:not(:disabled) { filter: brightness(1.06); transform: translateY(-1px); }
.draw-btn:hover:not(:disabled)::after { animation: brushSweep 0.34s ease-out both; }
.draw-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.draw-btn__cost {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.68rem;
  color: rgba(253, 242, 221, 0.76);
}
.draw-btn b {
  font-size: 1rem;
  letter-spacing: 0.2em;
  color: #fdf2dd;
  font-family: var(--font-sans);
  font-weight: 700;
}
.draw-btn--ten {
  background: linear-gradient(178deg, #b23a31 0%, #a32e27 55%, #85211c 100%);
}
.draw-btn--ten b { letter-spacing: 0.12em; }
.buy-row {
  flex: 0 0 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  font-size: 0.7rem;
}
.buy-row__owned {
  display: inline-flex;
  align-items: center;
  gap: 0.22rem;
  color: #cbb98d;
}
.buy-row__owned b { color: #e9d6ae; font-variant-numeric: tabular-nums; }
.buy-row__link {
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  border: 1px solid rgba(166, 124, 78, 0.45);
  background: rgba(72, 51, 28, 0.6);
  font-size: 0.68rem;
  color: var(--gold-2);
}
.buy-row__link:hover:not(:disabled) { border-color: rgba(201, 164, 110, 0.8); color: #e9d6ae; }
.buy-row__link:disabled { opacity: 0.4; cursor: not-allowed; }

/* ================= 天工石补给弹层 ================= */
.supply-mask { z-index: 96; }
.supply-modal {
  width: min(430px, 100%);
  padding: 1.15rem 1.25rem 1.25rem;
}
.supply-modal__lead {
  margin: 0 0 0.7rem;
  font-size: 0.82rem;
  line-height: 1.65;
  color: #cbb98d;
}
.supply-modal__lead b { color: #e9d6ae; }
.nw { white-space: nowrap; }
.supply-modal__row { display: flex; gap: 0.5rem; margin-bottom: 0.7rem; }
.supply-modal__res {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.18rem 0.5rem;
  border-radius: 999px;
  font-size: 0.74rem;
  color: #f0e0bb;
  border: 1px solid rgba(166, 124, 78, 0.26);
  background: rgba(0, 0, 0, 0.4);
}
.supply-modal__res b { color: #fff3d4; font-variant-numeric: tabular-nums; }
.res-chip__coin {
  width: 15px;
  height: 15px;
  display: inline-grid;
  place-items: center;
  border-radius: 50%;
  font-style: normal;
  font-size: 0.6rem;
  color: #4a2f06;
  background: linear-gradient(160deg, #ffe6a3, #d3a13c);
}
.supply-modal__opts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.45rem; }
.supply-opt {
  display: grid;
  gap: 2px;
  padding: 0.45rem 0.3rem 0.5rem;
  border-radius: 8px;
  border: 1px solid rgba(166, 124, 78, 0.4);
  background: linear-gradient(180deg, rgba(72, 51, 28, 0.92), rgba(32, 23, 14, 0.95));
  transition: 0.15s;
}
.supply-opt:hover:not(:disabled) {
  border-color: rgba(201, 164, 110, 0.82);
}
.supply-opt:disabled { opacity: 0.4; cursor: not-allowed; }
.supply-opt__qty {
  font-family: var(--font-serif);
  font-size: 0.88rem;
  letter-spacing: 0.04em;
  color: #e9d6ae;
}
.supply-opt__cost { font-size: 0.6rem; color: #a89877; }
.supply-modal__warn {
  margin: 0.6rem 0 0;
  font-size: 0.68rem;
  color: #e8a17a;
}
.supply-modal__warn a { color: var(--gold-2); text-decoration: underline; }
.past-note {
  margin: 0.8rem 0 0;
  text-align: center;
  font-size: 0.76rem;
  color: #e8c987;
}
.stats-row { margin: 0.7rem 0 0; text-align: center; font-size: 0.72rem; color: #b9a276; }
.stats-row b { color: #f4e2b0; }

/* ---------------- 右侧大奖架 ---------------- */
.shelf-col { display: grid; gap: 0.9rem; }
.shelf {
  position: relative;
  border-radius: 2px;
  padding: 0.55rem 0.6rem 0.7rem;
  border: 1px solid rgba(166, 124, 78, 0.24);
  background-color: var(--ink-700);
  background-image: linear-gradient(170deg, rgba(45, 39, 32, 0.94), rgba(24, 21, 18, 0.96));
}
.shelf::after {
  content: '';
  position: absolute;
  left: 5%;
  right: 5%;
  top: 0;
  height: 2px;
  background-image: var(--tex-drybrush);
  background-repeat: repeat-x;
  background-size: 240px 16px;
  opacity: 0.2;
  pointer-events: none;
}
/* 绸带改成朱砂／墨色布条 */
.shelf__ribbon {
  display: inline-block;
  margin: 0 0 0.6rem 0.2rem;
  padding: 2px 12px;
  font-family: var(--font-brush);
  font-size: 0.76rem;
  letter-spacing: 0.14em;
  border-radius: 1px;
  color: #f7e9d0;
  clip-path: polygon(0 0, 100% 0, calc(100% - 8px) 50%, 100% 100%, 0 100%);
}
.shelf--blue .shelf__ribbon { background: linear-gradient(160deg, #6b6257, #3d372f); }
.shelf--red .shelf__ribbon { background: linear-gradient(160deg, #a8322b, #7d1d19); }
.shelf__cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.45rem;
}
.prize-card {
  position: relative;
  aspect-ratio: 3 / 4.1;
  border-radius: 2px;
  overflow: hidden;
  border: 1px solid rgba(166, 124, 78, 0.34);
  background: rgba(18, 15, 13, 0.6);
}
.prize-card img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.prize-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 52%, rgba(18, 15, 13, 0.86));
}
.prize-card__glyph {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-family: var(--font-brush);
  font-size: 1.2rem;
  color: var(--gold-2);
}
/* 史诗标签＝小篆刻戳 */
.prize-card__tag {
  position: absolute;
  z-index: 2;
  top: 3px;
  right: 3px;
  font-family: var(--font-brush);
  font-size: 0.6rem;
  padding: 1px 4px;
  border-radius: 1px;
  color: #f7e9d0;
  background: linear-gradient(158deg, #9e2b25, #7d1d19);
  box-shadow: inset 0 0 0 1px rgba(247, 233, 208, 0.3);
  transform: rotate(-3deg);
}
.prize-card__owned {
  position: absolute;
  z-index: 2;
  left: 3px;
  top: 3px;
  font-family: var(--font-brush);
  font-size: 0.6rem;
  padding: 1px 4px;
  border-radius: 1px;
  color: #e8ebdc;
  background: rgba(92, 104, 78, 0.86);
  transform: rotate(-3deg);
}
.prize-card__name {
  position: absolute;
  z-index: 2;
  left: 4px;
  right: 4px;
  bottom: 3px;
  font-size: 0.62rem;
  color: var(--paper);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---------------- 规则 ---------------- */
.rules-panel {
  background-color: rgba(26, 23, 20, 0.94);
  background-image: none;
}
.rules { margin: 0.2rem 0 0; padding-left: 1.1rem; display: grid; gap: 0.4rem; }
.rules li { font-size: 0.74rem; line-height: 1.75; color: var(--paper-mute); }
.rules-src {
  display: inline-block;
  margin-top: 0.55rem;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  color: var(--gold-2);
  border-bottom: 1px solid rgba(166, 124, 78, 0.42);
}
.rules-src:hover { color: var(--gold); }
.src-note { margin: 1rem 0 0; font-size: 0.7rem; }

@media (max-width: 1320px) {
  .if--edge-l { width: clamp(46px, 6.6vw, 84px); opacity: 0.7; }
  .if--edge-r { width: clamp(78px, 9.4vw, 126px); opacity: 0.74; }
  .if--flag { width: 44px; height: 136px; }
  .bi--blade { width: 40%; }
}
@media (max-width: 1180px) {
  .if--edge-r, .if--flag, .if--dust, .if--seal-b { display: none; }
  .if--edge-l { width: 44px; opacity: 0.26; }
  .if--ticks { width: 34px; opacity: 0.34; }
  .if--floor { height: 120px; opacity: 0.68; }
  .if--seal-a { opacity: 0.16; }
}
@media (max-width: 940px) {
  .if--edge-l, .if--ticks, .if--seal-a { display: none; }
  .if--floor { height: 100px; opacity: 0.6; }
}
@media (max-width: 1060px) {
  .palace-main { grid-template-columns: 1fr; }
  .shelf-col { grid-template-columns: 1fr 1fr; align-items: start; }
  .rules-panel { grid-column: 1 / -1; }
}
@media (max-width: 720px) {
  .palace-banner { grid-template-columns: 140px 1fr; }
  .banner-currency { grid-column: 1 / -1; flex-direction: row; display: flex; padding: 0 1rem 0.9rem; }
  .shelf-col { grid-template-columns: 1fr; }
  .board-actions { flex-direction: column; }
  .board-wrap { padding: 0.7rem 0.55rem 0.75rem; }
  .tile { padding: 5% 2.5% 6%; }
}
</style>
