<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ItemGlyph from '../components/ItemGlyph.vue'
import ResultModal from '../components/ResultModal.vue'
import { useToast } from '../composables/useToast'
import { useAuth } from '../stores/auth'

const props = defineProps({ pool: { type: String, required: true } })

const auth = useAuth()
const router = useRouter()
const { success: toastSuccess, error: toastError } = useToast()

const data = ref(null)
const loading = ref(true)
const pulling = ref(false)
const result = ref(null)
const modalOpen = ref(false)
const activeTier = ref('all')

// 商店里与当前卡池消耗道具同名的那件商品（招募令 / 雁翎甲）
const shopItem = ref(null)
const buying = ref(false)

const isHero = computed(() => props.pool === 'hero')

const groups = computed(() => {
  if (!data.value) return []
  return data.value.tiers
    .map((tier) => {
      const items = data.value.entries.filter((e) => e.tier === tier.level)
      const weights = items.map((i) => i.weight)
      const probs = items.map((i) => i.probability)
      return {
        level: tier.level,
        label: tier.label,
        rarity: tier.rarity,
        note: tier.note,
        count: items.length,
        weightMin: weights.length ? Math.min(...weights) : 0,
        weightMax: weights.length ? Math.max(...weights) : 0,
        probMin: probs.length ? Math.min(...probs) : 0,
        probMax: probs.length ? Math.max(...probs) : 0,
        probability: tier.probability ?? 0,
        items,
      }
    })
    .filter((g) => g.items.length)
    .sort((a, b) => a.level - b.level)
})

const range = (lo, hi, fix = 0) =>
  (lo === hi ? lo.toFixed(fix) : `${lo.toFixed(fix)}–${hi.toFixed(fix)}`)

// 皮肤收集：官方按「已收集款数」逐级解锁皮肤分级
const skinGate = computed(() => {
  if (!data.value || isHero.value) return null
  return {
    owned: data.value.owned_skins ?? 0,
    grade: data.value.unlocked_grade ?? 1,
    next: data.value.next_grade_at ?? null,
    thresholds: data.value.grade_thresholds || [],
  }
})

const pullNote = computed(() =>
  isHero.value
    ? '重复武将不折算将魂，会作为重复卡留在背包，可在背包里手动分解'
    : '重复皮肤不折算雁翎，会留在背包可手动分解；集满 25 款以上解锁更高分级',
)

/** 皮肤名拆成「皮肤 / 武将」两行，窄格子里也能看全 */
const splitName = (item) => {
  if (item.kind !== 'skin') return { main: item.name, sub: '' }
  const [skin, hero] = item.name.split('·')
  return { main: skin, sub: hero || '' }
}

const visibleGroups = computed(() =>
  activeTier.value === 'all'
    ? groups.value
    : groups.value.filter((g) => g.level === Number(activeTier.value)),
)

const maxPulls = computed(() => data.value?.max_pulls ?? 10)
const owned = computed(() => data.value?.owned_cost_item ?? 0)
const canPull = (n) => owned.value >= n && !pulling.value

const unitPrice = computed(() => shopItem.value?.price ?? 0)
const canBuy = (n) => shopItem.value && !buying.value && auth.yuanbao >= unitPrice.value * n

const RARITY_NAME = {
  legendary: '传说', epic: '史诗', rare: '稀有',
  fine: '精良', good: '精品', common: '普通',
}

async function loadShop() {
  try {
    const res = await api.shop()
    shopItem.value = res.items.find((i) => i.name === data.value?.cost_item) || null
    auth.setYuanbao(res.yuanbao)
  } catch {
    shopItem.value = null
  }
}

async function buySupply(n) {
  if (!canBuy(n)) return
  buying.value = true
  try {
    const res = await api.buyItem(shopItem.value.key, n)
    auth.setYuanbao(res.yuanbao)
    data.value.owned_cost_item = res.owned
    toastSuccess(`购入「${res.name}」× ${res.count}，花费 ${res.spent.toLocaleString('zh-CN')} 元宝`)
  } catch (err) {
    toastError(err.message)
  } finally {
    buying.value = false
  }
}

async function load() {
  loading.value = true
  activeTier.value = 'all'
  try {
    data.value = await api.pool(props.pool)
    await loadShop()
  } catch (err) {
    toastError(err.message)
    router.replace('/')
  } finally {
    loading.value = false
  }
}

async function pull(n) {
  if (pulling.value) return
  if (owned.value < n) {
    const tip = shopItem.value
      ? `「${data.value.cost_item}」不足（需要 ${n}，当前 ${owned.value}）。可以开盒掉落，也可以下方直接买。`
      : `「${data.value.cost_item}」不足，需要 ${n} 个，当前 ${owned.value} 个。开盒才有得抽。`
    toastError(tip)
    return
  }
  pulling.value = true
  modalOpen.value = false
  try {
    const [res] = await Promise.all([
      api.pull(props.pool, n),
      new Promise((r) => setTimeout(r, 560)),
    ])
    auth.setYuanbao(res.yuanbao)
    data.value.owned_cost_item = res.owned_cost_item
    result.value = res
    modalOpen.value = true
    // 皮肤池按「已收集款数」解锁分级：抽到新皮肤可能刚好看够数，卡池要按新分级
    // 重新归一，顶部「已收集 / 下一档」也要跟着走。拉取失败不影响本次结果展示。
    if (props.pool === 'skin') {
      try {
        data.value = await api.pool('skin')
      } catch {
        /* 静默：下一次进入页面会重新拉 */
      }
    }
  } catch (err) {
    toastError(err.message)
  } finally {
    pulling.value = false
  }
}

watch(() => props.pool, load)
onMounted(load)
</script>

<template>
  <div class="shell recruit-page">
    <div class="crumbs">
      <router-link to="/" class="crumb">大厅</router-link>
      <span class="crumb-sep">/</span>
      <span class="crumb crumb--current">{{ isHero ? '武将招募' : '皮肤收集' }}</span>
    </div>

    <div class="pool-tabs">
      <router-link to="/recruit/hero" class="pool-tab" :class="{ active: isHero }">武将招募</router-link>
      <router-link to="/recruit/skin" class="pool-tab" :class="{ active: !isHero }">皮肤收集</router-link>
    </div>

    <div v-if="loading" class="empty">正在清点卡池……</div>

    <template v-else-if="data">
      <section class="pool-head panel">
        <div class="pool-head__main">
          <h1 class="page-title">{{ data.name }}</h1>
          <p class="subtle pool-head__desc">{{ data.description }}</p>
          <div class="pool-head__stats">
            <div class="stat-tile">
              <div class="stat-tile__label">当前卡池</div>
              <div class="stat-tile__value">{{ data.entries.length }}</div>
            </div>
            <div class="stat-tile">
              <div class="stat-tile__label">权重总和</div>
              <div class="stat-tile__value">{{ data.total_weight.toLocaleString('zh-CN') }}</div>
            </div>
            <div v-if="skinGate" class="stat-tile">
              <div class="stat-tile__label">已收集皮肤</div>
              <div class="stat-tile__value">{{ skinGate.owned }}</div>
            </div>
            <div class="stat-tile">
              <div class="stat-tile__label">{{ data.cost_item }} 持有</div>
              <div class="stat-tile__value">{{ owned }}</div>
            </div>
          </div>

          <p v-if="data.source" class="pool-head__source">数据来源：{{ data.source }}</p>

          <div v-if="skinGate" class="grade-gate">
            <div class="grade-gate__head">
              <span class="grade-gate__title">皮肤收集分级</span>
              <span class="grade-gate__now">已解锁 1–{{ skinGate.grade }} 级</span>
            </div>
            <div class="grade-gate__bar">
              <span
                v-for="t in skinGate.thresholds"
                :key="t.grade"
                class="grade-gate__dot"
                :class="{ 'is-on': t.grade <= skinGate.grade }"
              >
                {{ t.grade }}
              </span>
            </div>
            <p class="grade-gate__tip">
              <template v-if="skinGate.next">
                再收集
                <b>{{ Math.max(0, skinGate.next - skinGate.owned) }}</b>
                款皮肤（累计 {{ skinGate.next }} 款）即可解锁更高一级，池子会跟着变大。
              </template>
              <template v-else>已解锁全部皮肤分级。</template>
            </p>
          </div>
        </div>

        <div class="pool-head__actions">
          <div class="pull-orb" :class="{ 'is-pulling': pulling }">
            <span>{{ isHero ? '将' : '皮' }}</span>
          </div>
          <p v-if="!data.entries.length" class="pool-empty">
            本期皮肤已全部收集，等下一期吧。
          </p>
          <button class="btn btn-primary" :disabled="!canPull(1)" @click="pull(1)">
            单抽 · 1 {{ data.cost_item }}
          </button>
          <button class="btn btn-gold" :disabled="!canPull(10)" @click="pull(10)">
            十连 · 10 {{ data.cost_item }}
          </button>

          <div v-if="shopItem" class="buy-row">
            <span class="buy-row__label">商店补给 · {{ unitPrice.toLocaleString('zh-CN') }} 元宝 / 个</span>
            <button
              class="btn btn-sm btn-ghost"
              :disabled="!canBuy(1)"
              @click="buySupply(1)"
            >
              买 1 个 · {{ unitPrice.toLocaleString('zh-CN') }} 元宝
            </button>
            <button
              class="btn btn-sm btn-ghost"
              :disabled="!canBuy(10)"
              @click="buySupply(10)"
            >
              买 10 个 · {{ (unitPrice * 10).toLocaleString('zh-CN') }} 元宝
            </button>
            <router-link to="/shop" class="buy-row__link">去商店 →</router-link>
          </div>

          <p class="subtle" style="font-size: 0.73rem; text-align: center; margin: 0.2rem 0 0">
            {{ pullNote }}
          </p>
        </div>
      </section>

      <section class="panel panel--pad" style="margin-top: 1.1rem">
        <div class="panel__head">
          <h3>卡池一览</h3>
          <div class="tier-filter">
            <button class="chip chip--sm" :class="{ 'chip--active': activeTier === 'all' }" @click="activeTier = 'all'">
              全部
            </button>
            <button
              v-for="g in groups"
              :key="g.level"
              class="chip chip--sm"
              :class="{ 'chip--active': activeTier === String(g.level) }"
              @click="activeTier = String(g.level)"
            >
              {{ g.label }} · {{ g.count }}
            </button>
          </div>
        </div>

        <div v-for="g in visibleGroups" :key="g.level" class="tier-block">
          <div class="tier-block__head" :class="`r-${g.rarity}`">
            <span class="tier-block__level">{{ g.label }}</span>
            <span class="tier-block__label">
              {{ g.note }} · 共 {{ g.count }} {{ isHero ? '名' : '款' }}
            </span>
            <span class="tier-block__weight">
              权重 {{ range(g.weightMin, g.weightMax) }}
            </span>
            <span class="tier-block__prob">
              合计 {{ g.probability.toFixed(2) }}% · 单件 {{ range(g.probMin, g.probMax, 3) }}%
            </span>
          </div>
          <div class="tier-block__grid">
            <div
              v-for="item in g.items"
              :key="item.key"
              class="pool-item"
              :class="`r-${item.rarity}`"
              :title="isHero ? `武将分级 ${item.grade} · 权重 ${item.weight}` : `皮肤分级 ${item.grade} · 权重 ${item.weight}`"
            >
              <ItemGlyph :name="item.name" :kind="item.kind" :rarity="item.rarity" :size="28" />
              <span class="pool-item__text">
                <span class="pool-item__name">{{ splitName(item).main }}</span>
                <span v-if="splitName(item).sub" class="pool-item__sub">
                  {{ splitName(item).sub }}
                </span>
              </span>
            </div>
          </div>
        </div>
      </section>
    </template>

    <ResultModal
      :open="modalOpen"
      :data="result"
      :title="data?.name || '招募结果'"
      :loading="pulling"
      :again-label="`再抽 ${result?.count || 1} 次`"
      @close="modalOpen = false"
      @again="pull(result?.count || 1)"
    />
  </div>
</template>

<style scoped>
.recruit-page { padding-top: 1.8rem; }

.crumbs { display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; margin-bottom: 1.1rem; }
.crumb { color: var(--paper-mute); }
.crumb:hover { color: var(--gold); }
.crumb--current { color: var(--paper-dim); }
.crumb-sep { color: #4d453a; }

.pool-tabs { display: flex; gap: 0.4rem; margin-bottom: 1.1rem; flex-wrap: wrap; }
/* 竹简小牌，激活只加一道赭石短线 */
.pool-tab {
  position: relative;
  padding: 0.46rem 1.05rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.24);
  background: linear-gradient(180deg, rgba(58, 50, 42, 0.68), rgba(33, 29, 25, 0.86));
  color: var(--paper-dim);
  font-family: var(--font-brush);
  font-size: 0.94rem;
  letter-spacing: 0.1em;
  transition: color 0.18s, border-color 0.18s, background 0.18s;
}
.pool-tab:hover { color: var(--paper); border-color: rgba(166, 124, 78, 0.5); }
.pool-tab.active {
  color: var(--paper);
  border-color: rgba(166, 124, 78, 0.46);
  background: linear-gradient(180deg, rgba(74, 64, 53, 0.82), rgba(40, 35, 30, 0.9));
}
.pool-tab.active::after {
  content: '';
  position: absolute;
  left: 20%;
  right: 20%;
  bottom: -1px;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold) 16%, var(--gold-2) 76%, transparent);
  pointer-events: none;
}

.pool-head {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 1.5rem;
  padding: 1.5rem 1.6rem;
  background:
    radial-gradient(60% 90% at 92% 10%, rgba(179, 38, 47, 0.18), transparent 62%),
    linear-gradient(170deg, rgba(38, 33, 29, 0.92), rgba(16, 14, 13, 0.96));
}
.pool-head__desc { margin: 0.7rem 0 1.1rem; font-size: 0.85rem; line-height: 1.8; max-width: 46em; }
.pool-head__source {
  margin: 0.9rem 0 0;
  font-size: 0.72rem;
  color: var(--paper-mute);
  letter-spacing: 0.02em;
}

/* 皮肤收集分级 */
.grade-gate {
  margin-top: 0.9rem;
  padding: 0.7rem 0.85rem;
  border-radius: 2px;
  border: 1px dashed rgba(166, 124, 78, 0.3);
  background: rgba(166, 124, 78, 0.05);
  max-width: 46em;
}
.grade-gate__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
}
.grade-gate__title { font-family: var(--font-brush); font-size: 0.88rem; color: #d8c9a8; }
.grade-gate__now { font-size: 0.74rem; color: var(--paper-dim); font-variant-numeric: tabular-nums; }
.grade-gate__bar { display: flex; gap: 0.28rem; flex-wrap: wrap; }
.grade-gate__dot {
  min-width: 26px;
  padding: 1px 6px;
  text-align: center;
  border-radius: 2px;
  font-size: 0.68rem;
  color: #6d6354;
  border: 1px solid rgba(166, 124, 78, 0.18);
  font-variant-numeric: tabular-nums;
  transition: 0.2s;
}
.grade-gate__dot.is-on {
  color: #f0e0c0;
  border-color: rgba(201, 164, 110, 0.6);
  background: rgba(201, 164, 110, 0.16);
}
.grade-gate__tip { margin: 0.5rem 0 0; font-size: 0.72rem; color: var(--paper-mute); line-height: 1.75; }
.grade-gate__tip b { color: var(--gold-2); font-variant-numeric: tabular-nums; }

.pool-empty {
  font-size: 0.76rem;
  color: var(--gold-2);
  text-align: center;
  margin: 0;
}
.pool-head__stats { display: flex; gap: 0.7rem; flex-wrap: wrap; }
.pool-head__stats .stat-tile { min-width: 120px; flex: 1; }

.pool-head__actions {
  display: grid;
  gap: 0.6rem;
  align-content: center;
  min-width: 248px;
}
.pull-orb {
  width: 58px;
  height: 58px;
  margin: 0 auto 0.3rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-family: var(--font-serif);
  font-size: 1.5rem;
  color: var(--gold-2);
  background: radial-gradient(circle at 34% 28%, #b3323a, #5d1218 72%);
  box-shadow: 0 0 0 1px rgba(201, 164, 110, 0.34), inset 0 0 18px -8px rgba(0, 0, 0, 0.9);
  animation: floatSlow 5s ease-in-out infinite;
}
.pull-orb.is-pulling { animation: spin 0.8s linear infinite; }

.buy-row {
  display: grid;
  gap: 0.4rem;
  padding: 0.55rem 0.6rem;
  border-radius: 8px;
  border: 1px dashed rgba(166, 124, 78, 0.26);
  background: rgba(166, 124, 78, 0.045);
}
.buy-row__label {
  font-size: 0.7rem;
  color: var(--paper-mute);
  text-align: center;
  letter-spacing: 0.04em;
}
.buy-row__btns { display: flex; gap: 0.4rem; }
.buy-row .btn { font-size: 0.72rem; padding-inline: 0.5rem; white-space: nowrap; }
.buy-row__link { font-size: 0.7rem; color: var(--paper-mute); text-align: center; transition: 0.2s; }
.buy-row__link:hover { color: var(--gold); }

.tier-filter { display: flex; gap: 0.35rem; flex-wrap: wrap; justify-content: flex-end; }
.chip--sm { flex: none; padding: 0.3rem 0.6rem; font-size: 0.74rem; }

.tier-block { margin-top: 1.2rem; }
.tier-block__head {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding-bottom: 0.5rem;
  margin-bottom: 0.7rem;
  border-bottom: 1px solid color-mix(in srgb, var(--rc, #888) 26%, transparent);
  flex-wrap: wrap;
}
.tier-block__level {
  font-family: var(--font-serif);
  font-size: 0.82rem;
  color: var(--rc);
  border: 1px solid color-mix(in srgb, var(--rc) 40%, transparent);
  border-radius: 3px;
  padding: 0 5px;
}
.tier-block__label { font-size: 0.84rem; color: var(--paper-dim); font-family: var(--font-serif); }
.tier-block__weight { font-size: 0.72rem; color: var(--paper-mute); margin-left: auto; }
.tier-block__prob { font-size: 0.72rem; color: var(--rc); font-variant-numeric: tabular-nums; }

.tier-block__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(136px, 1fr));
  gap: 0.5rem;
}
.pool-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.42rem 0.5rem;
  border-radius: 7px;
  border: 1px solid color-mix(in srgb, var(--rc) 22%, transparent);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.035), transparent);
  transition: 0.2s;
}
.pool-item:hover {
  border-color: color-mix(in srgb, var(--rc) 60%, transparent);
  background: var(--rc-soft);
}
.pool-item__text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  line-height: 1.35;
}
.pool-item__name {
  font-size: 0.79rem;
  color: var(--paper-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pool-item__sub {
  font-size: 0.66rem;
  color: var(--paper-mute);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 860px) {
  .pool-head { grid-template-columns: 1fr; }
  .pool-head__actions { grid-template-columns: 1fr 1fr; min-width: 0; }
  .pool-head__actions .pull-orb,
  .pool-head__actions p { grid-column: 1 / -1; }
  .buy-row { grid-column: 1 / -1; }
}
</style>
