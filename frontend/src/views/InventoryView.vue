<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import ItemGlyph from '../components/ItemGlyph.vue'
import { useToast } from '../composables/useToast'

const { success: toastSuccess, error: toastError } = useToast()

const loading = ref(true)
const data = ref({ items: [], heroes: [], skins: [], total: 0 })
const tab = ref('items')

// 分解是二次点击确认：第一次点亮按钮，第二次才真的分解，防误触
const pending = ref('')
const busy = ref('')

const tabs = computed(() => [
  { key: 'items', label: '道具', count: data.value.items.length },
  { key: 'heroes', label: '武将', count: data.value.heroes.length },
  { key: 'skins', label: '皮肤', count: data.value.skins.length },
])

const current = computed(() => data.value[tab.value] || [])

const groupByKind = (list) => {
  const order = { legendary: 0, epic: 1, rare: 2, fine: 3, good: 4, common: 5 }
  return [...list].sort((a, b) => (order[a.rarity] ?? 9) - (order[b.rarity] ?? 9))
}

const RARITY_NAME = {
  legendary: '传说', epic: '史诗', rare: '稀有',
  fine: '精良', good: '精品', common: '普通',
}

/** 重复的武将 / 皮肤可以分解，最后一份留着 */
const spareOf = (item) => (item.kind === 'item' ? 0 : Math.max(0, item.qty - 1))

async function decompose(item) {
  if (busy.value) return
  if (pending.value !== item.key) {
    pending.value = item.key
    return
  }
  busy.value = item.key
  const n = spareOf(item)
  try {
    const res = await api.decompose(item.key, n)
    item.qty = res.qty
    const target = data.value.items.find((i) => i.key === res.gained.key)
    if (target) {
      target.qty += res.gained.qty
    } else {
      data.value.items.push({
        key: res.gained.key,
        name: res.gained.name,
        kind: 'item',
        rarity: res.gained.rarity || 'fine',
        qty: res.gained.qty,
      })
    }
    toastSuccess(`分解 ${res.decomposed} 份「${res.name}」，获得 ${res.gained.qty} ${res.gained.name}`)
  } catch (err) {
    toastError(err.message)
  } finally {
    busy.value = ''
    pending.value = ''
  }
}

/** 可开启的道具：拿到时是未开启的包裹，玩家自己点开才结算 */
const OPENABLE = new Set(['item:silver_pile'])

async function openPack(item, count = 1) {
  if (busy.value) return
  const n = Math.min(count, item.qty)
  if (n <= 0) return
  busy.value = item.key
  try {
    const res = await api.openItem(item.key, n)
    item.qty = res.qty
    const target = data.value.items.find((i) => i.key === res.gained.key)
    if (target) {
      target.qty += res.gained.qty
    } else {
      data.value.items.push({
        key: res.gained.key,
        name: res.gained.name,
        kind: 'item',
        rarity: res.gained.rarity || 'common',
        qty: res.gained.qty,
      })
    }
    data.value.total += res.gained.qty - res.opened
    toastSuccess(
      `开启 ${res.opened} 个「${res.name}」，获得「${res.gained.name}」×${res.gained.qty.toLocaleString('zh-CN')}`,
    )
  } catch (err) {
    toastError(err.message)
  } finally {
    busy.value = ''
  }
}

onMounted(async () => {
  try {
    data.value = await api.inventory()
  } catch (err) {
    toastError(err.message)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="shell inv-page">
    <header class="inv-head">
      <div>
        <h1 class="page-title">背包 <span class="seal">战利品</span></h1>
        <p class="subtle" style="margin: 0.5rem 0 0">
          共 <b class="gold">{{ data.total }}</b> 件物品 · 武将 {{ data.hero_count }} 名 · 皮肤
          {{ data.skin_count }} 款
        </p>
        <p class="subtle inv-hint">
          招募与皮肤收集抽到的重复卡不会自动折算，会直接留在背包里；多出来的那几份点
          <b class="gold">分解</b> 可换成将魂 / 雁翎，最后一份始终保留。
        </p>
      </div>
    </header>

    <div class="inv-tabs">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="inv-tab"
        :class="{ active: tab === t.key }"
        @click="tab = t.key"
      >
        {{ t.label }}
        <span class="inv-tab__count">{{ t.count }}</span>
      </button>
    </div>

    <div v-if="loading" class="empty">正在翻箱倒柜……</div>

    <div v-else-if="!current.length" class="panel empty">
      {{ tab === 'heroes' ? '还没有武将，开盒或招募都能拿。' : tab === 'skins' ? '皮肤栏空空如也，雁翎甲了解一下。' : '道具都空了，说明你开盒还不够勤。' }}
    </div>

    <div v-else class="grid inv-grid">
      <div
        v-for="item in groupByKind(current)"
        :key="item.key"
        class="item-card"
        :class="`r-${item.rarity}`"
      >
        <ItemGlyph :name="item.name" :kind="item.kind" :rarity="item.rarity" :size="44" />
        <div class="item-card__name">{{ item.name }}</div>
        <div class="item-card__qty">× {{ item.qty.toLocaleString('zh-CN') }}</div>
        <span class="rarity-tag" :class="`r-${item.rarity}`">{{ RARITY_NAME[item.rarity] }}</span>
        <button
          v-if="spareOf(item) > 0"
          class="item-card__dec"
          :class="{ 'is-armed': pending === item.key, 'is-busy': busy === item.key }"
          :disabled="!!busy"
          @click="decompose(item)"
        >
          {{ pending === item.key ? `确认分解 ×${spareOf(item)}` : `分解 ×${spareOf(item)}` }}
        </button>
        <button
          v-if="OPENABLE.has(item.key)"
          class="item-card__open"
          :disabled="!!busy"
          @click="openPack(item, 1)"
        >
          开启
        </button>
        <button
          v-if="OPENABLE.has(item.key) && item.qty > 1"
          class="item-card__open item-card__open--all"
          :disabled="!!busy"
          @click="openPack(item, item.qty)"
        >
          全开 ×{{ item.qty }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.inv-page { padding-top: 2.2rem; }
.inv-head { margin-bottom: 1.6rem; }
.inv-hint { margin: 0.55rem 0 0; font-size: 0.76rem; line-height: 1.7; max-width: 48em; }

/* 重复卡的分解按钮：第一次点亮，第二次才执行（赭石金小竹简） */
.item-card__dec {
  margin-top: 0.15rem;
  padding: 0.16rem 0.5rem;
  border-radius: 2px;
  font-family: var(--font-sans);
  font-size: 0.66rem;
  letter-spacing: 0.04em;
  color: var(--gold-2);
  border: 1px dashed rgba(166, 124, 78, 0.5);
  background: rgba(166, 124, 78, 0.1);
  cursor: pointer;
  transition: 0.18s;
  font-variant-numeric: tabular-nums;
}
.item-card__dec:hover {
  color: #f0e0c0;
  border-color: var(--gold);
  background: rgba(166, 124, 78, 0.2);
}
.item-card__dec.is-armed {
  color: #241a0e;
  font-weight: 700;
  border-style: solid;
  border-color: rgba(240, 224, 194, 0.4);
  background: linear-gradient(180deg, #c69a66, #a67c4e 62%, #8a6438);
}
.item-card__dec:disabled { cursor: default; opacity: 0.6; }

/* 「一堆银币」这类包裹：开启才掷出数量（朱砂小钮，不用绿） */
.item-card__open {
  margin-top: 0.15rem;
  padding: 0.16rem 0.55rem;
  border-radius: 2px;
  font-family: var(--font-sans);
  font-size: 0.66rem;
  letter-spacing: 0.04em;
  color: #f2dcc0;
  border: 1px solid rgba(158, 43, 37, 0.62);
  background: linear-gradient(180deg, rgba(158, 43, 37, 0.46), rgba(125, 29, 25, 0.56));
  cursor: pointer;
  transition: 0.18s;
  font-variant-numeric: tabular-nums;
}
.item-card__open:hover:not(:disabled) {
  color: #fff3e0;
  border-color: rgba(200, 80, 68, 0.82);
  background: linear-gradient(180deg, rgba(178, 56, 46, 0.6), rgba(140, 34, 28, 0.66));
}
.item-card__open:disabled { cursor: default; opacity: 0.55; }
.item-card__open--all { color: #e8cfae; border-style: dashed; }

/* Tab：竹简小牌，激活只加一道朱砂墨痕 */
.inv-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 1.3rem;
}
.inv-tab {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.46rem 1rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.24);
  background: linear-gradient(180deg, rgba(58, 50, 42, 0.68), rgba(33, 29, 25, 0.86));
  color: var(--paper-dim);
  font-family: var(--font-brush);
  font-size: 0.96rem;
  letter-spacing: 0.12em;
  cursor: pointer;
  transition: color 0.18s, border-color 0.18s, background 0.18s;
}
.inv-tab:hover { color: var(--paper); border-color: rgba(166, 124, 78, 0.5); }
.inv-tab.active {
  color: var(--paper);
  border-color: rgba(166, 124, 78, 0.46);
  background: linear-gradient(180deg, rgba(74, 64, 53, 0.82), rgba(40, 35, 30, 0.9));
}
.inv-tab.active::after {
  content: '';
  position: absolute;
  left: 18%;
  right: 18%;
  bottom: -1px;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--crimson-2) 12%, var(--crimson) 70%, transparent);
  pointer-events: none;
}
.inv-tab__count {
  font-family: var(--font-num);
  font-size: 0.7rem;
  padding: 0 5px;
  border-radius: 2px;
  background: rgba(166, 124, 78, 0.16);
  color: var(--gold-2);
  font-variant-numeric: tabular-nums;
}

.inv-grid {
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 0.75rem;
}
</style>
