<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import BoxArt from '../components/BoxArt.vue'
import { mediaUrl, focusPosition } from '../assets/media.js'
import { useToast } from '../composables/useToast'

const { error: toastError } = useToast()

const loading = ref(true)
const boxes = ref([])
const yearTab = ref('current')
const broken = ref(new Set())

// 在售 = 还在当期上架的盒子；往期按年份归档，可整年过滤
const yearTabs = computed(() => {
  const years = [...new Set(boxes.value.map((b) => b.year).filter(Boolean))]
  return [
    { key: 'current', label: `热门 ${boxes.value.filter((b) => b.kind !== 'past').length}` },
    { key: 'all', label: `盒子 ${boxes.value.length}` },
    ...years.sort().reverse().map((y) => ({
      key: String(y),
      label: `${y} ${boxes.value.filter((b) => b.year === y).length}`,
    })),
  ]
})

const shown = computed(() => {
  if (yearTab.value === 'all') return boxes.value
  if (yearTab.value === 'current') return boxes.value.filter((b) => b.kind !== 'past')
  return boxes.value.filter((b) => String(b.year) === yearTab.value)
})

// 每盒的主推大奖 = 权3武将（盒子同名主推），而非 0.005% 的年度权1；
// 规则：在武将/皮肤里取概率最低且 ≥0.008% 的那格（权1=0.005% 被排除）
const featuredOf = (box) => {
  const prizes = (box.entries || []).filter(
    (e) => (e.kind === 'hero' || e.kind === 'skin') && e.name,
  )
  if (!prizes.length) return null
  const sorted = [...prizes].sort((a, b) => a.probability - b.probability)
  return sorted.find((e) => e.probability >= 0.008) || sorted[0]
}

const thumbSrc = (box) => {
  const f = featuredOf(box)
  if (!f || broken.value.has(`${f.kind}:${f.name}:${box.id}`)) return ''
  return mediaUrl(f.name, f.kind)
}
const markBroken = (box) => {
  const f = featuredOf(box)
  if (!f) return
  const next = new Set(broken.value)
  next.add(`${f.kind}:${f.name}:${box.id}`)
  broken.value = next
}

// 奖品摘要：武将 / 皮肤 / 大额道具（将魂、史诗宝珠），与官方列表页口径一致
const summaryText = (box) => {
  const parts = []
  const entries = [...(box.entries || [])].sort((a, b) => a.probability - b.probability)
  for (const e of entries) {
    if (e.kind === 'hero' || e.kind === 'skin') {
      parts.push(e.qty > 1 ? `${e.name}*${e.qty}` : e.name)
    } else if (
      (e.name === '将魂' && e.qty >= 100) ||
      (e.name === '史诗宝珠' && e.qty >= 1)
    ) {
      parts.push(`${e.name}*${e.qty}`)
    }
    if (parts.length >= 6) break
  }
  return parts.join('、')
}

const tagText = (box) => {
  if (box.kind !== 'past') return '热卖中'
  if (!box.released) return '往期复刻'
  const [y, m, d] = box.released.split('-')
  return `${y}.${Number(m)}.${Number(d)} 往期`
}

onMounted(async () => {
  try {
    const res = await api.boxes()
    boxes.value = res.boxes
  } catch (err) {
    toastError(err.message)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="shell treasure">
    <!-- 战场水墨气氛层：只做「场」，不画人物/兵器/旗帜主体。
         固定贴视口 —— 滚动时形成被墨框住的感觉；z-index -1 保证永远在卡片之下 -->
    <div class="battle-field" aria-hidden="true">
      <span class="bf bf--mist"></span>
      <span class="bf bf--edge-l"></span>
      <span class="bf bf--edge-r"></span>
      <span class="bf bf--floor"></span>
      <span class="bf bf--flag"></span>
      <span class="bf bf--splash bf--splash-a"></span>
      <span class="bf bf--splash bf--splash-b"></span>
      <span class="bf bf--spray"></span>
    </div>

    <div class="crumbs">
      <router-link to="/" class="crumb">大厅</router-link>
      <span class="crumb-sep">/</span>
      <span class="crumb crumb--current">奇珍异宝</span>
    </div>

    <div v-if="loading" class="empty">正在搬盒子……</div>
    <div v-else-if="!boxes.length" class="empty">宝阁空空，连盒子都跑光了。</div>

    <template v-else>
      <div class="treasure-tabs">
        <button
          v-for="t in yearTabs"
          :key="t.key"
          class="treasure-tab"
          :class="{ 'treasure-tab--active': yearTab === t.key }"
          @click="yearTab = t.key"
        >
          {{ t.label }}
        </button>
        <span class="tab-brush" aria-hidden="true"></span>
        <router-link to="/odds" class="treasure-odds-link">
          <i class="seal-stamp seal-stamp--sm" aria-hidden="true">示</i>
          权重公示 →
        </router-link>
      </div>

      <section v-if="shown.length" class="box-list">
        <article
          v-for="box in shown"
          :key="box.id"
          class="box-row"
          :class="{ 'is-past': box.kind === 'past' }"
        >
          <div class="box-row__thumb">
            <img
              v-if="thumbSrc(box)"
              :src="thumbSrc(box)"
              :alt="box.name"
              :style="{ objectPosition: focusPosition(featuredOf(box).kind) }"
              loading="lazy"
              @error="markBroken(box)"
            />
            <BoxArt v-else :theme="box.theme" :size="86" />
          </div>

          <div class="box-row__body">
            <div class="box-row__title">
              <h2>{{ box.name }}</h2>
              <span v-if="box.kind !== 'past'" class="hot-badge">热</span>
            </div>
            <p class="box-row__summary">{{ summaryText(box) }}</p>
            <div class="box-row__meta">
              <span class="tag-red" :class="{ 'tag-red--ghost': box.kind === 'past' }">
                {{ tagText(box) }}
              </span>
              <span class="subtle box-row__price">{{ box.price }} 元宝 / 个</span>
            </div>
            <div class="box-row__actions">
              <router-link :to="`/box/${box.id}`" class="btn-gray">查看详情</router-link>
              <router-link :to="`/box/${box.id}`" class="btn-blue">开始开盒</router-link>
            </div>
          </div>
        </article>
      </section>

      <div v-else class="empty">这一年没有上架礼盒。</div>

      <!-- 卡片组下方的收笔：短墨痕 + 一枚小印，只放在一处的记忆点 -->
      <div v-if="shown.length" class="aftermath" aria-hidden="true">
        <span class="aftermath__dot"></span>
        <span class="aftermath__stroke"></span>
        <i class="aftermath__seal">藏</i>
      </div>
    </template>
  </div>
</template>

<style scoped>
.treasure { padding-top: 1.8rem; }

/* ============================================================
   战场水墨气氛层
   三层结构：焦墨底（body）+ 气氛层（战雾/远山/残旗 4%–7%）
   + 边界层（左右枯笔 6%–9%、底部沉积 5%–8%）。
   全部 fixed 且 pointer-events: none，不参与布局、不挡点击。
   ============================================================ */
.battle-field {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  overflow: hidden;
}
.bf { position: absolute; display: block; pointer-events: none; }

/* 1) 大面积淡焦墨晕染：让空区不死黑，但也不画任何具体形象 */
.bf--mist {
  inset: 0;
  background:
    radial-gradient(64% 38% at 18% 22%, rgba(166, 124, 78, 0.095), transparent 72%),
    radial-gradient(54% 34% at 84% 44%, rgba(158, 43, 37, 0.072), transparent 74%),
    radial-gradient(72% 42% at 50% 74%, rgba(126, 106, 80, 0.088), transparent 78%);
}

/* 2) 左侧：竖向枯笔残边（左重）—— 焦墨压边 + 干墨丝 + 内层渐隐 */
.bf--edge-l {
  left: 0;
  top: 0;
  bottom: 0;
  width: clamp(34px, 5.6vw, 112px);
  background-image:
    var(--tex-brush-v),
    var(--tex-edge-v),
    linear-gradient(
      90deg,
      rgba(7, 6, 5, 0.7) 0%,
      rgba(9, 8, 6, 0.42) 34%,
      rgba(13, 11, 9, 0.13) 70%,
      transparent 100%
    );
  background-size: 100% 100%, 100% 100%, 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.9;
  -webkit-mask-image: linear-gradient(
    90deg,
    #000 0%,
    rgba(0, 0, 0, 0.78) 40%,
    rgba(0, 0, 0, 0.24) 76%,
    transparent 100%
  );
  mask-image: linear-gradient(
    90deg,
    #000 0%,
    rgba(0, 0, 0, 0.78) 40%,
    rgba(0, 0, 0, 0.24) 76%,
    transparent 100%
  );
}
/* 旧甲片纹：只留一道极淡的短甲片线，若隐若现，不做成梯子 */
.bf--edge-l::after {
  content: '';
  position: absolute;
  left: 0;
  top: 18%;
  bottom: 22%;
  width: 30%;
  background-image: repeating-linear-gradient(
    180deg,
    rgba(230, 214, 182, 0.055) 0 1px,
    transparent 1px 34px
  );
  opacity: 0.7;
  -webkit-mask-image: linear-gradient(90deg, #000, transparent 88%);
  mask-image: linear-gradient(90deg, #000, transparent 88%);
}

/* 3) 右侧：淡墨晕染边（右轻）—— 只有一小片赭朱晕与更稀的干墨丝 */
.bf--edge-r {
  right: 0;
  top: 0;
  bottom: 0;
  width: clamp(22px, 3.8vw, 76px);
  background-image:
    var(--tex-brush-v),
    var(--tex-edge-v),
    radial-gradient(150% 40% at 100% 22%, rgba(166, 124, 78, 0.1), transparent 72%),
    radial-gradient(130% 34% at 100% 70%, rgba(158, 43, 37, 0.062), transparent 76%);
  background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.55;
  -webkit-mask-image: linear-gradient(270deg, #000, rgba(0, 0, 0, 0.4) 52%, transparent 100%);
  mask-image: linear-gradient(270deg, #000, rgba(0, 0, 0, 0.4) 52%, transparent 100%);
}

/* 4) 底部：战雾压底 —— 山脊只在中段露一道，最底部再压回去 */
.bf--floor {
  left: 0;
  right: 0;
  bottom: 0;
  height: clamp(200px, 42vh, 440px);
  background-image: var(--tex-ridge);
  background-size: 100% 62%;
  background-position: center bottom;
  background-repeat: no-repeat;
}
/* 压暗层必须压在山之上，否则山体填充会让底部反而变亮 */
.bf--floor::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to top,
    rgba(7, 6, 5, 0.72) 0%,
    rgba(9, 8, 6, 0.5) 22%,
    rgba(15, 13, 11, 0.22) 52%,
    rgba(26, 23, 20, 0) 80%
  );
  pointer-events: none;
}
/* 旧牛皮纸折痕：一条短斜折痕 + 两道更短的余痕，绝不横贯全屏 */
.bf--floor::after {
  content: '';
  position: absolute;
  left: 7%;
  bottom: 30%;
  width: 34%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(230, 214, 182, 0.075) 18%,
    rgba(230, 214, 182, 0.05) 64%,
    transparent
  );
  transform: rotate(-1.4deg);
  box-shadow:
    44vw 26px 0 -0.4px rgba(230, 214, 182, 0.045),
    -1vw 52px 0 -0.6px rgba(230, 214, 182, 0.032);
  pointer-events: none;
}

/* 5) 泼墨团：卡片下方的两大片空区各落一团，轮廓被 displacement 打散成不规则墨渍。
      卡片底不透明，墨团只会从空处透出来，不会脏到卡面 */
.bf--splash {
  background-image: var(--tex-splash);
  background-size: 100% 100%;
  background-repeat: no-repeat;
  pointer-events: none;
}
.bf--splash-a {
  left: -6%;
  bottom: 15%;
  width: clamp(340px, 46vw, 640px);
  height: clamp(340px, 46vw, 640px);
  background-position: left bottom;
  opacity: 0.95;
}
/* 同一张笔触镜像一次，右边那道就不会和左边重复 */
.bf--splash-b {
  left: 41%;
  bottom: 4%;
  width: clamp(300px, 40vw, 560px);
  height: clamp(300px, 40vw, 560px);
  background-position: center bottom;
  transform: scaleX(-1);
  opacity: 0.85;
}

/* 6) 极远残旗：只在右下角露出半截轮廓，不加模糊（线条本来就只有 1px 宽） */
.bf--flag {
  right: 2%;
  bottom: 5%;
  width: clamp(150px, 16vw, 280px);
  height: clamp(96px, 10vw, 176px);
  background-image: var(--tex-flag);
  background-size: contain;
  background-repeat: no-repeat;
  background-position: right bottom;
  opacity: 0.5;
}

/* 7) 零星飞墨：颗粒状不成团，铺在右上与左下两片空区 */
.bf--spray {
  inset: 0;
  background-image: var(--tex-spray);
  background-size: 200px 200px;
  opacity: 0.72;
  -webkit-mask-image:
    radial-gradient(62% 48% at 86% 26%, #000, transparent 74%),
    radial-gradient(52% 44% at 10% 88%, #000, transparent 76%);
  -webkit-mask-composite: source-over;
  mask-image:
    radial-gradient(62% 48% at 86% 26%, #000, transparent 74%),
    radial-gradient(52% 44% at 10% 88%, #000, transparent 76%);
  mask-composite: add;
}

/* 卡片组下方的收笔：短横枯笔 + 两点飞墨 + 一枚朱砂小印 */
.aftermath {
  position: relative;
  height: 0;
  margin-top: 0.55rem;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  padding-right: 4%;
  pointer-events: none;
}
.aftermath__stroke {
  width: clamp(68px, 11vw, 142px);
  height: 3px;
  background-image: var(--tex-drybrush);
  background-repeat: repeat-x;
  background-size: 240px 16px;
  opacity: 0.24;
}
.aftermath__dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(166, 124, 78, 0.46);
  box-shadow:
    7px -3px 0 -0.6px rgba(166, 124, 78, 0.28),
    -8px 2px 0 -1px rgba(166, 124, 78, 0.22);
}
.aftermath__seal {
  display: grid;
  place-items: center;
  width: 19px;
  height: 19px;
  border-radius: 1px;
  font-family: var(--font-brush);
  font-style: normal;
  font-size: 0.68rem;
  line-height: 1;
  color: rgba(217, 152, 138, 0.82);
  background: rgba(158, 43, 37, 0.18);
  border: 1px solid rgba(158, 43, 37, 0.52);
  box-shadow: inset 0 0 0 1px rgba(247, 233, 208, 0.08);
  transform: rotate(-4deg);
}

.crumbs { display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; margin-bottom: 1rem; }
.crumb { color: var(--paper-mute); }
.crumb:hover { color: var(--gold); }
.crumb--current { color: var(--paper-dim); }
.crumb-sep { color: #4d453a; }

/* 页签：竹简式短块，选中只压一道朱砂墨痕 */
.treasure-tabs {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
/* 页签与「权重公示」之间那一大片空：一笔横扫过去的枯墨，压在页签同一行的中线上 */
.tab-brush {
  position: absolute;
  left: 33%;
  right: 19%;
  top: 50%;
  height: 26px;
  margin-top: -13px;
  pointer-events: none;
  background-image: var(--tex-brush-h);
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.72;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 9%, #000 72%, transparent 97%);
  mask-image: linear-gradient(90deg, transparent, #000 9%, #000 72%, transparent 97%);
}
.treasure-tab {
  position: relative;
  padding: 0.34rem 0.9rem;
  border-radius: 2px;
  font-size: 0.8rem;
  font-family: var(--font-sans);
  color: var(--paper-mute);
  border: 1px solid rgba(166, 124, 78, 0.2);
  background: linear-gradient(180deg, rgba(58, 50, 42, 0.5), rgba(33, 29, 25, 0.8));
  cursor: pointer;
  transition: color 0.16s, border-color 0.16s, background 0.16s;
}
.treasure-tab:hover { color: var(--paper-dim); border-color: rgba(166, 124, 78, 0.45); }
.treasure-tab--active {
  color: var(--paper);
  background: linear-gradient(180deg, rgba(70, 60, 48, 0.72), rgba(40, 34, 28, 0.86));
  border-color: rgba(166, 124, 78, 0.44);
}
.treasure-tab--active::after {
  content: '';
  position: absolute;
  left: 9%;
  right: 9%;
  bottom: -1px;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--crimson-2) 14%, var(--crimson) 68%, transparent);
}
.treasure-odds-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-left: auto;
  font-size: 0.76rem;
  color: var(--paper-mute);
}
.treasure-odds-link:hover { color: var(--gold-2); }

/* 列表卡片：宽屏两列排布，窄屏自动回落单列 */
.box-list {
  display: grid;
  gap: 0.7rem;
  grid-template-columns: repeat(auto-fit, minmax(min(520px, 100%), 1fr));
  align-items: start;
}
/* 旧宣纸底 + 枯笔飞白上沿，去掉原来的金色描边 */
.box-row {
  position: relative;
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 0.85rem;
  padding: 0.8rem 0.9rem 0.85rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.2);
  background-color: var(--ink-700);
  background-image: linear-gradient(172deg, rgba(45, 39, 32, 0.95), rgba(23, 20, 17, 0.97));
  overflow: hidden;
  transition: border-color 0.18s, transform 0.18s;
}
.box-row::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.07;
  background-image: var(--tex-fiber);
  background-size: 180px 180px;
}
.box-row::after {
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
.box-row:hover {
  border-color: rgba(166, 124, 78, 0.5);
  transform: translateY(-1px);
}
.box-row.is-past { opacity: 0.8; }

.box-row__thumb {
  position: relative;
  width: 96px;
  aspect-ratio: 3 / 4;
  border-radius: 2px;
  overflow: hidden;
  border: 1px solid rgba(166, 124, 78, 0.3);
  background: rgba(18, 15, 13, 0.6);
  display: grid;
  place-items: center;
}
.box-row__thumb img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
/* 插画不动，只压一层极淡宣纸暗角 */
.box-row__thumb::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(120% 100% at 50% 38%, transparent 52%, rgba(26, 23, 20, 0.4));
}
.box-row__thumb :deep(svg) { transform: scale(0.42); transform-origin: center; }

.box-row__body { display: grid; gap: 0.3rem; align-content: start; }
.box-row__title { display: flex; align-items: center; gap: 0.45rem; }
.box-row__title h2 {
  margin: 0;
  font-family: var(--font-brush);
  font-size: 1.1rem;
  font-weight: 400;
  letter-spacing: 0.06em;
  color: var(--paper);
}
/* 角标＝朱砂方印 */
.hot-badge {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 1px;
  font-family: var(--font-brush);
  font-size: 0.66rem;
  color: #f7e9d0;
  background: linear-gradient(158deg, #a8322b, #86201b);
  box-shadow: inset 0 0 0 1px rgba(247, 233, 208, 0.36);
  transform: rotate(-3deg);
}
.box-row__summary {
  margin: 0;
  font-size: 0.76rem;
  line-height: 1.65;
  color: var(--paper-mute);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.box-row__meta { display: flex; align-items: center; gap: 0.6rem; }
/* 「热卖中 / 往期」＝朱砂小印 */
.tag-red {
  font-family: var(--font-brush);
  font-size: 0.66rem;
  padding: 1px 7px;
  border-radius: 1px;
  color: #f7e9d0;
  background: linear-gradient(158deg, #a8322b, #86201b);
  box-shadow: inset 0 0 0 1px rgba(247, 233, 208, 0.3);
  transform: rotate(-2deg);
}
.tag-red--ghost {
  color: #b9907f;
  background: rgba(158, 43, 37, 0.06);
  border: 1px solid rgba(158, 43, 37, 0.34);
  box-shadow: none;
  transform: none;
}
.box-row__price { font-size: 0.72rem; font-family: var(--font-num); }
.box-row__actions { display: flex; gap: 0.5rem; margin-top: 0.15rem; }
.btn-gray,
.btn-blue {
  position: relative;
  overflow: hidden;
  padding: 0.3rem 0.95rem;
  border-radius: 2px;
  font-size: 0.76rem;
  transition: color 0.16s, border-color 0.16s, filter 0.16s;
}
/* 暗墨竹简 */
.btn-gray {
  color: var(--paper-dim);
  border: 1px solid rgba(166, 124, 78, 0.24);
  background: linear-gradient(180deg, rgba(58, 50, 42, 0.6), rgba(33, 29, 25, 0.85));
}
.btn-gray:hover { color: var(--paper); border-color: rgba(166, 124, 78, 0.55); }
/* 朱砂战旗 + 旧皮革纹理 */
.btn-blue {
  color: #fdf2dd;
  background: linear-gradient(178deg, #a8322b 0%, #9e2b25 55%, #7d1d19 100%);
  border: 1px solid rgba(247, 233, 208, 0.28);
}
.btn-blue::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.14;
  pointer-events: none;
  background-image: var(--tex-fiber);
  background-size: 120px 120px;
}
.btn-blue::after {
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
.btn-blue:hover::after { animation: brushSweep 0.34s ease-out both; }
.btn-blue:hover { filter: brightness(1.05); }
.btn-gray:hover::after,
.btn-blue:hover::after { animation: brushSweep 0.34s ease-out both; }
.btn-gray::after {
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

@media (max-width: 620px) {
  .box-row { grid-template-columns: 78px minmax(0, 1fr); gap: 0.7rem; }
  .box-row__thumb { width: 78px; }
  .box-row__title h2 { font-size: 1rem; }
  .box-row__actions { margin-top: 0.1rem; }

  /* 窄屏边界收薄，别让墨边吃掉卡片左右的可读宽度 */
  .bf--edge-l { width: 20px; opacity: 0.7; }
  .bf--edge-l::after { display: none; }
  .bf--edge-r { width: 13px; opacity: 0.28; }
  .bf--floor { height: 34vh; }
  .bf--flag { right: -8%; opacity: 0.34; }
  .bf--spray { opacity: 0.28; }

  /* 页签会换行，那笔横墨无处可放，直接收掉 */
  .tab-brush { display: none; }
  .bf--splash-a { left: -18%; bottom: 2%; opacity: 0.7; }
  .bf--splash-b { left: 30%; bottom: 0%; opacity: 0.6; }
}
</style>
