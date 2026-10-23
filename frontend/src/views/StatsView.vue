<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import ItemGlyph from '../components/ItemGlyph.vue'
import { useToast } from '../composables/useToast'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const { error: toastError } = useToast()

const loading = ref(true)
const stats = ref(null)
const records = ref([])

const RARITY_NAME = {
  legendary: '传说', epic: '史诗', rare: '稀有',
  fine: '精良', good: '精品', common: '普通',
}
const RARITY_COLOR = {
  legendary: 'var(--gold-2)',
  epic: 'var(--crimson-2)',
  rare: 'var(--gold)',
  fine: '#7e8a6a',
  good: '#9a8a70',
  common: 'var(--paper-mute)',
}

const rarityRows = computed(() => {
  if (!stats.value) return []
  const total = stats.value.total_pulls || 1
  return ['legendary', 'epic', 'rare', 'fine', 'good', 'common']
    .map((r) => ({
      key: r,
      label: RARITY_NAME[r],
      count: stats.value.by_rarity[r] || 0,
      pct: ((stats.value.by_rarity[r] || 0) / total) * 100,
    }))
    .filter((r) => r.count > 0)
})

const maxDaily = computed(() =>
  Math.max(1, ...(stats.value?.daily || []).map((d) => d.pulls)),
)

const spent = computed(() => {
  if (!stats.value) return 0
  return (stats.value.box_stats || []).reduce((s, b) => s + (b.spent || 0), 0)
})

const boxNames = ref({})

const boxName = (id) => boxNames.value[id] || id || '未知'

const sourceName = (s) =>
  ({ box: '开盒', hero: '武将招募', skin: '皮肤抽取', palace: '天宫宝库', corridor: '梦之回廊' })[s] ||
  s

onMounted(async () => {
  try {
    const [s, r, b] = await Promise.all([api.stats(), api.records(40), api.boxes()])
    stats.value = s
    records.value = r.records
    boxNames.value = Object.fromEntries(b.boxes.map((x) => [x.id, x.name]))
    auth.setYuanbao(s.yuanbao)
  } catch (err) {
    toastError(err.message)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="shell stats-page">
    <header>
      <h1 class="page-title">战绩 <span class="seal">复盘</span></h1>
      <p class="subtle" style="margin: 0.5rem 0 0">
        数字不会说谎，它只会告诉你：为什么别人一发入魂，而你只抽到菜篮子。
      </p>
    </header>

    <div v-if="loading" class="empty">正在算账……</div>

    <template v-else-if="stats">
      <section class="grid grid-4" style="margin-bottom: 1.1rem">
        <div class="stat-tile">
          <div class="stat-tile__label">总抽取次数</div>
          <div class="stat-tile__value">{{ stats.total_pulls }}</div>
        </div>
        <div class="stat-tile">
          <div class="stat-tile__label">开盒消耗元宝</div>
          <div class="stat-tile__value">{{ spent.toLocaleString('zh-CN') }}</div>
        </div>
        <div class="stat-tile">
          <div class="stat-tile__label">欧气值</div>
          <div class="stat-tile__value">{{ stats.luck }}</div>
        </div>
        <div class="stat-tile">
          <div class="stat-tile__label">传说获取</div>
          <div class="stat-tile__value">{{ stats.by_rarity.legendary || 0 }}</div>
        </div>
      </section>

      <div class="stats-grid">
        <section class="panel panel--pad">
          <div class="panel__head">
            <h3>稀有度分布</h3>
            <span class="subtle">{{ stats.rarity_kinds }} 种</span>
          </div>

          <div v-if="!rarityRows.length" class="empty">还没有数据，盒子在等你。</div>
          <div v-else class="rarity-chart">
            <div v-for="row in rarityRows" :key="row.key" class="rarity-chart__row">
              <div class="rarity-chart__label">
                <span class="rarity-tag" :class="`r-${row.key}`">{{ row.label }}</span>
                <span class="rarity-chart__count">{{ row.count }} 件</span>
              </div>
              <div class="rarity-chart__track">
                <div
                  class="rarity-chart__fill"
                  :style="{ width: `${Math.max(2, row.pct)}%`, background: RARITY_COLOR[row.key] }"
                />
              </div>
              <span class="rarity-chart__pct">{{ row.pct.toFixed(1) }}%</span>
            </div>
          </div>

          <hr class="hr-fade" />

          <div class="panel__head">
            <h3>来源分布</h3>
          </div>
          <div class="source-list">
            <div v-for="(v, k) in stats.by_source" :key="k" class="source-row">
              <span>{{ sourceName(k) }}</span>
              <b class="gold">{{ v }}</b>
            </div>
            <div v-if="!Object.keys(stats.by_source).length" class="subtle">暂无</div>
          </div>
        </section>

        <section class="panel panel--pad">
          <div class="panel__head">
            <h3>近 7 日抽取</h3>
          </div>
          <div v-if="!stats.daily.length" class="empty">近七天一次没抽，定力惊人。</div>
          <div v-else class="daily-chart">
            <div v-for="d in stats.daily" :key="d.date" class="daily-col">
              <span class="daily-col__value">{{ d.pulls }}</span>
              <div class="daily-col__bar-wrap">
                <div
                  class="daily-col__bar"
                  :style="{ height: `${Math.max(6, (d.pulls / maxDaily) * 100)}%` }"
                />
              </div>
              <span class="daily-col__label">{{ d.date.slice(5) }}</span>
            </div>
          </div>

          <hr class="hr-fade" />

          <div class="panel__head">
            <h3>高光时刻</h3>
          </div>
          <div v-if="!stats.highlights.length" class="subtle">还没有史诗以上记录，继续努力。</div>
          <div v-else class="highlight-list">
            <div
              v-for="(h, i) in stats.highlights"
              :key="i"
              class="highlight"
              :class="`r-${h.rarity}`"
            >
              <ItemGlyph :name="h.name" :kind="h.kind" :rarity="h.rarity" :size="26" />
              <span class="highlight__name">{{ h.name }}</span>
              <span v-if="(h.total || h.qty) > 1" class="highlight__qty">×{{ h.total || h.qty }}</span>
              <span class="rarity-tag" :class="`r-${h.rarity}`">{{ RARITY_NAME[h.rarity] }}</span>
            </div>
          </div>
        </section>
      </div>

      <section class="panel panel--pad" style="margin-top: 1.1rem">
        <div class="panel__head">
          <h3>抽取流水</h3>
          <span class="subtle">最近 {{ records.length }} 条</span>
        </div>

        <div v-if="!records.length" class="empty">没有记录。</div>
        <div v-else class="table-wrap">
          <table class="record-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>来源</th>
                <th>物品</th>
                <th>数量</th>
                <th>稀有度</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in records" :key="r.id">
                <td class="mono">{{ new Date(r.created_at).toLocaleString('zh-CN', { hour12: false }) }}</td>
                <td>
                  {{ sourceName(r.source) }}
                  <span v-if="r.source === 'box' && r.box_id" class="subtle">
                    · {{ boxName(r.box_id) }}</span
                  >
                </td>
                <td :style="{ color: RARITY_COLOR[r.rarity] }">{{ r.name }}</td>
                <td class="mono">×{{ r.qty }}</td>
                <td>
                  <span class="rarity-tag" :class="`r-${r.rarity}`">{{ RARITY_NAME[r.rarity] }}</span>
                </td>
                <td class="subtle">{{ r.note || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.stats-page { padding-top: 2.2rem; }

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.1rem;
}

.rarity-chart { display: grid; gap: 0.85rem; }
.rarity-chart__row {
  display: grid;
  grid-template-columns: 150px 1fr 54px;
  align-items: center;
  gap: 0.7rem;
}
.rarity-chart__label { display: flex; align-items: center; gap: 0.5rem; }
.rarity-chart__count { font-size: 0.76rem; color: var(--paper-mute); font-variant-numeric: tabular-nums; }
.rarity-chart__track {
  height: 8px;
  border-radius: 0;
  background: rgba(236, 226, 202, 0.07);
  overflow: hidden;
}
.rarity-chart__fill {
  height: 100%;
  border-radius: 0;
  animation: growX 0.8s cubic-bezier(0.2, 0.8, 0.3, 1) both;
  transform-origin: left;
  opacity: 0.9;
}
.rarity-chart__pct {
  font-size: 0.78rem;
  color: var(--paper-dim);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.source-list { display: grid; gap: 0.5rem; }
.source-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  color: var(--paper-dim);
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(236, 226, 202, 0.09);
}

.daily-chart {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  height: 150px;
  padding-top: 0.5rem;
}
.daily-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  height: 100%;
}
.daily-col__value { font-size: 0.68rem; color: var(--gold); font-variant-numeric: tabular-nums; }
.daily-col__bar-wrap {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.daily-col__bar {
  width: min(30px, 70%);
  border-radius: 3px 3px 0 0;
  background: linear-gradient(180deg, var(--crimson-2), rgba(125, 26, 33, 0.35));
  animation: riseIn 0.6s ease both;
}
.daily-col__label { font-size: 0.66rem; color: var(--paper-mute); }

.highlight-list { display: grid; gap: 0.4rem; }
.highlight {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.4rem 0.5rem;
  border-radius: 2px;
  background: linear-gradient(180deg, rgba(45, 39, 32, 0.82), rgba(26, 23, 20, 0.9));
  border: 1px solid rgba(166, 124, 78, 0.16);
  border-left: 2px solid color-mix(in srgb, var(--rc) 60%, transparent);
}
.highlight__name { flex: 1; font-size: 0.83rem; color: var(--paper); }
.highlight__qty { font-size: 0.74rem; color: var(--gold-2); font-variant-numeric: tabular-nums; }

.table-wrap { overflow-x: auto; }
.record-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
  min-width: 640px;
}
.record-table th {
  text-align: left;
  font-weight: 500;
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  color: var(--paper-mute);
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid rgba(166, 124, 78, 0.26);
  white-space: nowrap;
}
.record-table td {
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid rgba(236, 226, 202, 0.07);
  color: var(--paper-dim);
}
.record-table tr:hover td { background: rgba(166, 124, 78, 0.06); }
.mono { font-variant-numeric: tabular-nums; }

@media (max-width: 980px) {
  .stats-grid { grid-template-columns: 1fr; }
  .rarity-chart__row { grid-template-columns: 120px 1fr 46px; }
}
</style>
