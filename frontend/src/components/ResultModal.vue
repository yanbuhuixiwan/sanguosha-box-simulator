<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import ItemGlyph from './ItemGlyph.vue'
import { mediaUrl, focusPosition } from '../assets/media.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '开盒结果' },
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  againLabel: { type: String, default: '再来一次' },
  againDisabled: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'again'])

const ORDER = { legendary: 0, epic: 1, rare: 2, fine: 3, good: 4, common: 5 }
const RARITY_NAME = {
  legendary: '传说', epic: '史诗', rare: '稀有',
  fine: '精良', good: '精品', common: '普通',
}

/**
 * 结算图里同一件东西只出现一次，数量累加。
 * 后端已经给了合并好的 items（含 dup：其中几份是重复的）；
 * 万一是老数据没有 items，就在前端按 key 现合并一遍。
 */
const rewards = computed(() => {
  const d = props.data
  if (!d) return []
  let list = d.items
  if (!Array.isArray(list) || list.length === 0) {
    const map = new Map()
    for (const r of d.results || []) {
      const cur = map.get(r.key)
      if (cur) {
        cur.qty += r.qty || 1
        if (r.duplicate) cur.dup = (cur.dup || 0) + 1
      } else {
        map.set(r.key, { ...r, qty: r.qty || 1, dup: r.duplicate ? 1 : 0 })
      }
    }
    list = [...map.values()]
  }
  return [...list].sort(
    (a, b) =>
      (ORDER[a.rarity] ?? 9) - (ORDER[b.rarity] ?? 9) ||
      (b.qty || 1) - (a.qty || 1) ||
      a.name.localeCompare(b.name, 'zh-CN'),
  )
})

const totalQty = computed(() => rewards.value.reduce((sum, r) => sum + (r.qty || 1), 0))

/** 本次抽到几件「已拥有」的重复卡 —— 它们不会折算，直接进背包 */
const dupTotal = computed(() => (props.data?.results || []).filter((r) => r.duplicate).length)

/** 结算格里的素材图：武将/皮肤整张铺满，道具居中放图标 */
const broken = ref(new Set())
function artSrc(item) {
  if (broken.value.has(item.key)) return ''
  return mediaUrl(item.name, item.kind)
}
function markBroken(item) {
  broken.value = new Set(broken.value).add(item.key)
}

const chips = computed(() => {
  const counts = props.data?.rarity_counts || {}
  return ['legendary', 'epic', 'rare']
    .filter((r) => counts[r])
    .map((r) => ({ rarity: r, label: RARITY_NAME[r], count: counts[r] }))
})

const source = computed(() => props.data?.box_name || props.title || '')

// 结算弹窗打开时窗口大小基本不会变，只在挂载/缩放时更新一次
const narrow = ref(window.innerWidth < 620)
const onResize = () => {
  narrow.value = window.innerWidth < 620
}
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

const columns = computed(() => {
  const n = rewards.value.length || 1
  const wide = n <= 6 ? n : n <= 8 ? 4 : 6 // 一屏排得下就排成一行
  // 窄屏最多三列，否则格子只剩五十来像素，名字全被截断
  return narrow.value ? Math.min(wide, 3) : wide
})

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${columns.value}, minmax(0, 1fr))`,
  maxWidth: `${columns.value * 124}px`,
}))

// 只抽到一两件时把弹窗收窄，别让牌匾孤零零地横在空桌子上
const modalStyle = computed(() => {
  const wide = columns.value * 124 + 150
  return { width: `min(${Math.max(380, Math.min(880, wide))}px, 100%)` }
})
</script>

<template>
  <div v-if="open" class="modal-mask" @click.self="emit('close')">
    <div class="res-modal" :style="modalStyle">
      <button class="res-close" aria-label="关闭" @click="emit('close')">✕</button>

      <div class="res-plaque">
        <span class="res-rule res-rule--l" />
        <h2 class="res-title">恭喜获得</h2>
        <span class="res-rule res-rule--r" />
      </div>

      <p class="res-source">
        <span class="res-source__name">{{ source }}</span>
        <span class="res-source__dot">·</span>
        <span>{{ data?.count ?? 0 }} 次</span>
        <span class="res-source__dot">·</span>
        <span>共 {{ rewards.length }} 种 {{ totalQty }} 件</span>
        <span v-if="data?.note" class="res-badge">{{ data.note }}</span>
        <span v-if="dupTotal" class="res-badge res-badge--dup">
          重复 {{ dupTotal }} 件未折算
        </span>
      </p>

      <div v-if="chips.length" class="res-chips">
        <span v-for="c in chips" :key="c.rarity" class="rarity-tag" :class="`r-${c.rarity}`">
          {{ c.label }} × {{ c.count }}
        </span>
      </div>

      <div v-if="!rewards.length" class="res-empty">这一手什么也没抽到，概率系统正在思考人生。</div>

      <div v-else class="res-grid" :style="gridStyle">
        <div
          v-for="(item, i) in rewards"
          :key="item.key"
          class="res-cell"
          :class="{ 'is-legendary': item.rarity === 'legendary' }"
          :style="{ animationDelay: `${Math.min(i * 55, 900)}ms` }"
        >
          <div class="res-art" :class="[`r-${item.rarity}`, { 'has-art': artSrc(item) }]">
            <img
              v-if="artSrc(item)"
              class="res-img"
              :src="artSrc(item)"
              :alt="item.name"
              decoding="async"
              :style="{ objectPosition: focusPosition(item.kind) }"
              @error="markBroken(item)"
            />
            <ItemGlyph
              v-else
              :name="item.name"
              :kind="item.kind"
              :rarity="item.rarity"
              :size="44"
              name-glyph
            />
            <span class="res-qty">×{{ item.qty || 1 }}</span>
            <span v-if="item.dup" class="res-dup">重复</span>
          </div>
          <div class="res-name" :title="item.name">{{ item.name }}</div>
        </div>
      </div>

      <div class="res-foot">
        <span class="res-cost">
          消耗
          <b>{{ (data?.cost_amount ?? data?.cost ?? 0).toLocaleString('zh-CN') }}</b>
          {{ data?.cost_item ? data.cost_item : '元宝' }}
        </span>
        <div class="res-actions">
          <button class="btn btn-ghost" @click="emit('close')">收下</button>
          <button class="btn btn-gold" :disabled="loading || againDisabled" @click="emit('again')">
            <span v-if="loading" class="spinner" />
            {{ loading ? '抽取中' : againLabel }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.res-modal {
  position: relative;
  width: min(880px, 100%);
  max-height: 90vh;
  overflow: auto;
  padding: 1.5rem 1.7rem 1.3rem;
  border-radius: 4px;
  border: 1px solid rgba(166, 124, 78, 0.28);
  background-color: var(--ink-700);
  background-image:
    radial-gradient(120% 78% at 50% -14%, rgba(158, 43, 37, 0.12), transparent 58%),
    linear-gradient(180deg, rgba(48, 41, 34, 0.96) 0%, rgba(28, 24, 21, 0.98) 52%, rgba(20, 17, 14, 1) 100%);
  box-shadow:
    0 40px 90px -30px #000,
    inset 0 0 0 1px rgba(166, 124, 78, 0.12),
    inset 0 0 90px -24px #000;
  animation: modalIn 0.34s cubic-bezier(0.16, 0.9, 0.28, 1) both;
}
.res-modal::before {
  content: '';
  position: absolute;
  inset: 7px;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.16);
  pointer-events: none;
}

.res-close {
  position: absolute;
  top: 0.55rem;
  right: 0.7rem;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  color: var(--paper-mute);
  font-size: 0.8rem;
  background: transparent;
  border: 1px solid transparent;
  transition: 0.2s;
  z-index: 2;
}
.res-close:hover {
  color: var(--paper);
  border-color: rgba(166, 124, 78, 0.35);
  background: rgba(166, 124, 78, 0.08);
}

/* ---------- 牌匾标题 ---------- */
.res-plaque {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  padding: 0.25rem 0 0.1rem;
}
.res-title {
  flex: none;
  font-family: var(--font-brush);
  font-size: clamp(1.55rem, 4.2vw, 2.2rem);
  letter-spacing: 0.2em;
  line-height: 1.2;
  padding-left: 0.2em;
  background: linear-gradient(180deg, #f6ead2 4%, #dcb98a 40%, #a67c4e 74%, #e3c99a 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  white-space: nowrap;
}
.res-rule {
  position: relative;
  flex: 1;
  height: 1px;
}
.res-rule--l {
  background: linear-gradient(90deg, transparent, rgba(166, 124, 78, 0.55));
}
.res-rule--r {
  background: linear-gradient(270deg, transparent, rgba(166, 124, 78, 0.55));
}
.res-rule::after {
  content: '';
  position: absolute;
  top: -2.5px;
  width: 6px;
  height: 6px;
  transform: rotate(45deg);
  background: var(--gold);
}
.res-rule--l::after { right: 0; }
.res-rule--r::after { left: 0; }

/* ---------- 来源与稀有度 ---------- */
.res-source {
  margin: 0.65rem 0 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.4rem;
  font-size: 0.76rem;
  color: var(--paper-mute);
  letter-spacing: 0.03em;
}
.res-source__name { color: var(--gold); font-family: var(--font-serif); letter-spacing: 0.08em; }
.res-source__dot { color: #4d453a; }
.res-badge {
  margin-left: 0.3rem;
  padding: 1px 7px;
  border-radius: 2px;
  font-size: 0.68rem;
  letter-spacing: 0.1em;
  color: #241a0e;
  background: linear-gradient(160deg, #c69a66, #a67c4e);
}
.res-badge--dup {
  color: #e8d9b5;
  background: rgba(166, 124, 78, 0.14);
  border: 1px solid rgba(166, 124, 78, 0.4);
  letter-spacing: 0.04em;
}

.res-chips {
  display: flex;
  justify-content: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-top: 0.6rem;
}

/* ---------- 奖励网格 ---------- */
.res-grid {
  display: grid;
  gap: 0.85rem 0.6rem;
  margin: 1.15rem auto 0;
  justify-content: center;
}

.res-cell {
  animation: cellIn 0.42s cubic-bezier(0.2, 0.9, 0.3, 1) both;
}
@keyframes cellIn {
  from { opacity: 0; transform: translateY(10px) scale(0.9); }
  to { opacity: 1; transform: none; }
}

.res-art {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 2px;
  display: grid;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--rc, #8d8474) 52%, #6b5236);
  background:
    radial-gradient(72% 62% at 50% 24%, var(--rc-soft, rgba(236, 226, 202, 0.08)), transparent 72%),
    linear-gradient(180deg, rgba(45, 39, 32, 0.94), rgba(26, 23, 20, 0.96));
  box-shadow: inset 0 0 20px -8px #000, 0 6px 14px -10px #000;
  overflow: hidden;
}

/* 素材图整张铺满卡片，稀有度描边与光晕还留在外框上 */
.res-art .res-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.res-art.has-art::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, transparent 58%, rgba(10, 7, 4, 0.55) 100%);
}

/* 图标在深木底上原本太糊，这里单独提亮一档；尺寸用百分比跟着格子走，移动端不会撑爆 */
.res-art :deep(.item-card__icon) {
  width: 56% !important;
  height: 56% !important;
  font-size: clamp(0.95rem, 1.75vw, 1.4rem) !important;
  background: radial-gradient(
    circle at 34% 28%,
    color-mix(in srgb, var(--rc) 38%, transparent),
    rgba(0, 0, 0, 0.34) 80%
  );
  border-color: color-mix(in srgb, var(--rc) 72%, transparent);
  color: color-mix(in srgb, var(--rc) 42%, #f0e3c8);
  font-weight: 600;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.85);
  box-shadow: inset 0 0 10px -4px #000;
}

.res-cell.is-legendary .res-art {
  border-color: rgba(201, 164, 110, 0.66);
  box-shadow: inset 0 0 20px -8px #000, inset 0 0 0 1px rgba(158, 43, 37, 0.32);
}

.res-qty {
  position: absolute;
  right: 4px;
  bottom: 2px;
  z-index: 2;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: #fff;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 1px 2px #000, 0 0 7px rgba(0, 0, 0, 0.95), 0 0 3px #000;
}

/* 重复卡不折算，只在这里标记一下 */
.res-dup {
  position: absolute;
  top: 3px;
  left: 3px;
  z-index: 2;
  padding: 0 4px;
  border-radius: 2px;
  font-size: 0.6rem;
  line-height: 1.5;
  letter-spacing: 0.04em;
  color: #f0e2c2;
  background: rgba(12, 9, 6, 0.72);
  border: 1px solid rgba(166, 124, 78, 0.45);
}

.res-name {
  margin-top: 0.42rem;
  font-size: 0.76rem;
  line-height: 1.3;
  text-align: center;
  color: #e6d9be;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.res-empty {
  padding: 2.6rem 0;
  text-align: center;
  color: var(--paper-mute);
  font-size: 0.85rem;
}

/* ---------- 底部 ---------- */
.res-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 1.4rem;
  padding-top: 0.95rem;
  border-top: 1px solid rgba(166, 124, 78, 0.16);
}
.res-cost { font-size: 0.76rem; color: var(--paper-mute); }
.res-cost b { color: var(--gold-2); font-weight: 600; }
.res-actions { display: flex; gap: 0.55rem; margin-left: auto; }

@keyframes modalIn {
  from { opacity: 0; transform: translateY(24px) scale(0.97); }
  to { opacity: 1; transform: none; }
}

@media (max-width: 620px) {
  .res-modal { padding: 1.2rem 1rem 1rem; }
  .res-title { letter-spacing: 0.14em; }
  .res-grid { gap: 0.6rem 0.45rem; }
  .res-name { font-size: 0.7rem; }
  .res-foot { justify-content: center; }
  .res-actions { width: 100%; margin-left: 0; }
  .res-actions .btn { flex: 1; }
}
</style>
