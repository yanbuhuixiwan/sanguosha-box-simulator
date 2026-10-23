<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import ProbabilityList from '../components/ProbabilityList.vue'
import { useToast } from '../composables/useToast'

const { error: toastError } = useToast()

const loading = ref(true)
const boxes = ref([])
const pools = ref([])
const palace = ref(null)
const corridor = ref(null)
const tab = ref('box')

// 74 只盒子全部展开会有上千张图标，默认只展开一只，其余按需展开
const expanded = ref(new Set())
const yearFilter = ref('all')

// 幸运值满时的大奖概率由后端按同一套权重算法给出，避免文案写死
const maxGrandText = computed(() => {
  const v = palace.value?.max_grand_probability
  return typeof v === 'number' ? `${v.toFixed(2)}%` : '1.50%'
})

const years = computed(() => {
  const set = new Set(boxes.value.map((b) => b.year).filter(Boolean))
  return [...set].sort((a, b) => b - a)
})

const shownBoxes = computed(() => {
  if (yearFilter.value === 'all') return boxes.value
  if (yearFilter.value === 'past') return boxes.value.filter((b) => b.kind === 'past')
  return boxes.value.filter((b) => String(b.year) === String(yearFilter.value))
})

const isOpen = (id) => expanded.value.has(id)

function toggleBox(id) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}

function expandAll() {
  expanded.value = new Set(shownBoxes.value.map((b) => b.id))
}

function collapseAll() {
  expanded.value = new Set()
}

onMounted(async () => {
  try {
    const res = await api.odds()
    boxes.value = res.boxes
    pools.value = res.pools.filter(Boolean)
    palace.value = res.palace || null
    corridor.value = res.corridor || null
    if (res.boxes.length) expanded.value = new Set([res.boxes[0].id])
  } catch (err) {
    toastError(err.message)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="shell odds-page">
    <header>
      <h1 class="page-title">概率公示 <span class="seal">明码</span></h1>
      <p class="subtle" style="margin: 0.5rem 0 0; max-width: 52em; line-height: 1.8">
        所有概率均由权重表直接计算：<b class="gold">单项概率 = 该项权重 ÷ 权重总和</b>。
      </p>
    </header>

    <div class="odds-tabs">
      <button class="odds-tab" :class="{ active: tab === 'box' }" @click="tab = 'box'">
        礼盒
      </button>
      <button class="odds-tab" :class="{ active: tab === 'pool' }" @click="tab = 'pool'">
        招募与抽皮
      </button>
      <button class="odds-tab" :class="{ active: tab === 'palace' }" @click="tab = 'palace'">
        天宫宝库
      </button>
      <button class="odds-tab" :class="{ active: tab === 'corridor' }" @click="tab = 'corridor'">
        梦之回廊
      </button>
    </div>

    <div v-if="loading" class="empty">正在核对账本……</div>

    <template v-else>
      <div v-if="tab === 'box'" class="odds-list">
        <div class="odds-filter">
          <button
            class="odds-chip"
            :class="{ active: yearFilter === 'all' }"
            @click="yearFilter = 'all'"
          >
            全部 {{ boxes.length }}
          </button>
          <button
            v-for="y in years"
            :key="y"
            class="odds-chip"
            :class="{ active: String(yearFilter) === String(y) }"
            @click="yearFilter = String(y)"
          >
            {{ y }}
          </button>
          <button
            class="odds-chip"
            :class="{ active: yearFilter === 'past' }"
            @click="yearFilter = 'past'"
          >
            往期
          </button>
          <span class="odds-filter__gap" />
          <button class="odds-chip odds-chip--ghost" @click="expandAll">全部展开</button>
          <button class="odds-chip odds-chip--ghost" @click="collapseAll">全部收起</button>
        </div>

        <p class="odds-hint subtle">
          共 {{ shownBoxes.length }} 只，点标题展开对应概率表。
        </p>

        <section v-for="box in shownBoxes" :key="box.id" class="panel panel--pad">
          <div class="panel__head">
            <button class="odds-toggle" :aria-expanded="isOpen(box.id)" @click="toggleBox(box.id)">
              <span class="odds-toggle__caret" :class="{ open: isOpen(box.id) }">▸</span>
              <h3>
                {{ box.name }} · {{ box.price }} 元宝 / 个
                <span v-if="box.kind === 'past'" class="odds-past">往期</span>
              </h3>
            </button>
            <span class="subtle">
              {{ box.entry_count }} 项 · 权重和 {{ box.total_weight.toLocaleString('zh-CN') }}
            </span>
          </div>
          <template v-if="isOpen(box.id)">
            <p v-if="box.bonus?.length" class="odds-bonus">
              开盒附赠：{{ box.bonus.map((b) => `${b.name} ×${b.qty}`).join(' · ') }}
              <span class="subtle">（每个盒子固定赠送，不参与下列概率）</span>
            </p>
            <ProbabilityList :entries="box.entries" :limit="50" />
          </template>
        </section>
      </div>

      <div v-else-if="tab === 'palace'" class="odds-list">
        <section v-if="palace" class="panel panel--pad">
          <div class="panel__head">
            <h3>{{ palace.name }} · 12 格奖池</h3>
            <span class="subtle">
              {{ palace.cost_item }} {{ palace.cost_price }} 元宝 / 颗 · 幸运值满
              {{ palace.pity_limit }} 必中
            </span>
          </div>
          <p class="odds-bonus">
            上表为幸运值 0 时的基础概率；幸运值会按比例放大红色大奖格，最高约
            {{ maxGrandText }}，满 {{ palace.pity_limit }} 点则必中大奖（中奖后清零，
            抽到已拥有的大奖返还 {{ palace.repeat_refund }} 颗天工石）。
          </p>
          <div class="group-row">
            <div v-for="g in palace.groups || []" :key="g.group" class="group-card">
              <span class="group-card__name">{{ g.group }}</span>
              <span class="group-card__p">{{ (g.probability ?? 0).toFixed(2) }}%</span>
              <span class="group-card__w">{{ g.cells }} 格 · 权重 {{ g.weight }}</span>
            </div>
          </div>
          <ProbabilityList :entries="palace.entries" :limit="20" />
        </section>
      </div>

      <div v-else-if="tab === 'corridor'" class="odds-list">
        <section v-if="corridor" class="panel panel--pad">
          <div class="panel__head">
            <h3>{{ corridor.name }} · {{ corridor.theme }}</h3>
            <span class="subtle">{{ corridor.cost_item }} {{ corridor.cost_price }} 元宝 / 颗</span>
          </div>
          <p class="odds-bonus">
            每次回想固定获得 1 份下列随机奖励 + 1 个记忆碎片，碎片新开概率见下方说明。
          </p>
          <ProbabilityList :entries="corridor.entries" :limit="20" />
          <p class="subtle" style="font-size: 0.76rem; margin: 0.9rem 0 0; line-height: 1.85">
            {{ corridor.fragment_rate_note }}
          </p>
        </section>
      </div>

      <div v-else class="odds-list">
        <section v-for="pool in pools" :key="pool.pool_id" class="panel panel--pad">
          <div class="panel__head">
            <h3>{{ pool.name }}</h3>
            <span class="subtle">
              消耗 {{ pool.cost_item }} ×{{ pool.cost_per_pull }} / 次 · {{ pool.entries.length }} 项
            </span>
          </div>

          <div class="tier-summary">
            <div v-for="tier in pool.tiers" :key="tier.level" class="tier-card" :class="`r-${tier.rarity}`">
              <span class="tier-card__lv">{{ tier.label }}</span>
              <span class="tier-card__label">{{ tier.count }} {{ pool.pool_id === 'hero' ? '名' : '款' }}</span>
              <span class="tier-card__w">{{ tier.note }}</span>
              <span class="tier-card__p">{{ (tier.probability ?? 0).toFixed(2) }}%</span>
            </div>
          </div>

          <p class="subtle" style="font-size: 0.76rem; margin: 0.9rem 0 0">
            概率 = 单件权重 ÷ 当前池权重总和（武将总权重 {{ pool.total_weight.toLocaleString('zh-CN') }}）。
            <template v-if="pool.pool_id === 'skin'">
              雁翎甲为「皮肤收集」池：按已收集款数逐级解锁皮肤分级，上表为全池（1–16 级）数据，
              游戏内只会从已解锁的分级里出。
            </template>
            <template v-else>
              武将分普通 / 精品 / 史诗三档，取自官方《武将招募权重公示》。
            </template>
          </p>
          <p v-if="pool.source" class="subtle" style="font-size: 0.72rem; margin: 0.35rem 0 0">
            数据来源：{{ pool.source }}
          </p>
        </section>
      </div>

      <p class="disclaimer">
        本页面仅用于概率演示。模拟器与腾讯《三国杀》官方无任何关联，不提供任何真实充值、交易或账号服务。
      </p>
    </template>
  </div>
</template>

<style scoped>
.odds-page { padding-top: 2.2rem; }

.odds-tabs {
  display: flex;
  gap: 0.4rem;
  margin: 1.4rem 0 1.1rem;
  flex-wrap: wrap;
}
/* 竹简小按钮，激活只加一道赭石短线，不铺亮底 */
.odds-tab {
  position: relative;
  padding: 0.46rem 1rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.24);
  background: linear-gradient(180deg, rgba(58, 50, 42, 0.68), rgba(33, 29, 25, 0.86));
  color: var(--paper-dim);
  font-family: var(--font-brush);
  font-size: 0.94rem;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: color 0.18s, border-color 0.18s, background 0.18s;
}
.odds-tab:hover { color: var(--paper); border-color: rgba(166, 124, 78, 0.5); }
.odds-tab.active {
  color: var(--paper);
  border-color: rgba(166, 124, 78, 0.46);
  background: linear-gradient(180deg, rgba(74, 64, 53, 0.82), rgba(40, 35, 30, 0.9));
}
.odds-tab.active::after {
  content: '';
  position: absolute;
  left: 20%;
  right: 20%;
  bottom: -1px;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold) 16%, var(--gold-2) 76%, transparent);
  pointer-events: none;
}

.odds-list { display: grid; gap: 1.1rem; }

.odds-filter {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.odds-filter__gap { flex: 1 1 12px; }
.odds-chip {
  padding: 0.26rem 0.68rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.22);
  background: rgba(40, 35, 30, 0.5);
  color: var(--paper-mute);
  font-size: 0.76rem;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: 0.18s;
}
.odds-chip:hover { color: var(--paper); border-color: rgba(166, 124, 78, 0.5); }
.odds-chip.active {
  color: var(--gold-2);
  border-color: rgba(166, 124, 78, 0.5);
  background: rgba(166, 124, 78, 0.14);
  box-shadow: inset 0 -2px 0 rgba(201, 164, 110, 0.62);
}
.odds-chip--ghost {
  font-size: 0.72rem;
  border-color: rgba(166, 124, 78, 0.3);
  background: rgba(236, 226, 202, 0.03);
}
.odds-hint { margin: -0.35rem 0 0; font-size: 0.72rem; }

/* 表头（每条概率表的标题条）：暗宣纸底 ＋ h3 前那一道短朱砂墨痕，无亮黄 */
.odds-list .panel__head {
  padding: 0.55rem 0.7rem 0.6rem;
  border-radius: 2px;
  border-bottom: 1px solid rgba(166, 124, 78, 0.18);
  background: linear-gradient(180deg, rgba(58, 50, 42, 0.55), rgba(33, 29, 25, 0.32));
}

.odds-toggle {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  background: none;
  border: 0;
  padding: 0;
  cursor: pointer;
  text-align: left;
}
.odds-toggle h3 { margin: 0; }
.odds-toggle:hover h3 { color: var(--gold-2); }
.odds-toggle__caret {
  display: inline-block;
  font-size: 0.72rem;
  color: var(--gold);
  transition: transform 0.18s;
}
.odds-toggle__caret.open { transform: rotate(90deg); }

.tier-summary {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.6rem;
}
.tier-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.7rem 0.8rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.18);
  border-left: 2px solid color-mix(in srgb, var(--rc) 62%, transparent);
  background: linear-gradient(180deg, rgba(45, 39, 32, 0.88), rgba(26, 23, 20, 0.94));
}
.tier-card__lv {
  font-family: var(--font-serif);
  font-size: 0.75rem;
  color: var(--rc);
  letter-spacing: 0.1em;
}
.tier-card__label { font-size: 0.88rem; color: var(--paper); font-family: var(--font-serif); }
.tier-card__w { font-size: 0.72rem; color: var(--paper-mute); }
.tier-card__p { font-size: 0.78rem; color: var(--rc); font-variant-numeric: tabular-nums; }

.disclaimer {
  margin-top: 1.6rem;
  font-size: 0.74rem;
  color: #6f6555;
  text-align: center;
  line-height: 1.9;
}

.odds-past {
  display: inline-block;
  margin-left: 0.45rem;
  padding: 1px 7px;
  border-radius: 3px;
  border: 1px solid rgba(160, 152, 138, 0.45);
  color: #a89e8e;
  font-size: 0.66rem;
  letter-spacing: 0.1em;
  vertical-align: 2px;
}

.odds-bonus {
  margin: -0.35rem 0 0.85rem;
  padding: 0.45rem 0.65rem;
  border-radius: 2px;
  border: 1px dashed rgba(166, 124, 78, 0.22);
  border-left: 2px solid rgba(166, 124, 78, 0.5);
  background: rgba(166, 124, 78, 0.05);
  font-size: 0.76rem;
  color: var(--gold-2);
}
.odds-bonus .subtle { color: var(--paper-mute); font-size: 0.7rem; }
.group-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.55rem;
  margin: 0 0 0.85rem;
}
.group-card {
  display: grid;
  gap: 0.12rem;
  padding: 0.5rem 0.7rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.22);
  background:
    repeating-linear-gradient(90deg, rgba(236, 226, 202, 0.025) 0 1px, transparent 1px 9px),
    linear-gradient(180deg, rgba(58, 50, 42, 0.6), rgba(31, 27, 23, 0.78));
}
.group-card__name { font-family: var(--font-serif); font-size: 0.86rem; color: var(--paper); letter-spacing: 0.1em; }
.group-card__p { font-size: 0.94rem; color: var(--gold-1); font-variant-numeric: tabular-nums; }
.group-card__w { font-size: 0.68rem; color: var(--paper-mute); }
</style>
