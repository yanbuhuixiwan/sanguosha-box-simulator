<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import BoxArt from '../components/BoxArt.vue'
import ItemGlyph from '../components/ItemGlyph.vue'
import ProbabilityList from '../components/ProbabilityList.vue'
import ResultModal from '../components/ResultModal.vue'
import { mediaUrl, focusPosition } from '../assets/media.js'
import { useToast } from '../composables/useToast'
import { useAuth } from '../stores/auth'

const props = defineProps({ id: { type: String, required: true } })

const auth = useAuth()
const router = useRouter()
const { error: toastError } = useToast()

const boxes = ref([])
const box = ref(null)
const loading = ref(true)
const opening = ref(false)
const result = ref(null)
const modalOpen = ref(false)
const count = ref(10)
const recent = ref([])
const breaking = ref(new Set())

const maxBulk = 50
const countOptions = [1, 5, 10, 20, 50]

const affordable = computed(() =>
  box.value ? Math.floor(auth.yuanbao / box.value.price) : 0,
)
const canOpen = computed(() => !opening.value && affordable.value >= 1)
const canOpenCount = computed(() => affordable.value >= count.value)
const costFor = (n) => (box.value ? box.value.price * n : 0)

// 右侧「稀世珍宝」卡：取权3主推武将（≥0.008% 中概率最低者），
// 而非 0.005% 的年度权1武将
const featured = computed(() => {
  if (!box.value) return null
  const prizes = (box.value.entries || []).filter(
    (e) => (e.kind === 'hero' || e.kind === 'skin') && e.name,
  )
  if (!prizes.length) return null
  const sorted = [...prizes].sort((a, b) => a.probability - b.probability)
  return sorted.find((e) => e.probability >= 0.008) || sorted[0]
})

const featuredArt = computed(() => {
  const f = featured.value
  if (!f || breaking.value.has(`${f.kind}:${f.name}`)) return ''
  return mediaUrl(f.name, f.kind)
})
const markBroken = (name, kind) => {
  const next = new Set(breaking.value)
  next.add(`${kind}:${name}`)
  breaking.value = next
}

// 「本盒累计打开」用 /stats 里按 box_id 聚合的 pulls：它覆盖全部历史，
// 而 records 只回最近 60 条（一次开盒会产出多条记录，用记录求和会被截断）。
const boxPulls = ref(0)
const openedTotal = computed(() =>
  boxPulls.value || recent.value.reduce((s, r) => s + (r.pulls || 1), 0),
)

async function load() {
  loading.value = true
  try {
    const [boxRes, recRes, statsRes] = await Promise.all([
      api.boxes(),
      api.records(60, { source: 'box', boxId: props.id }),
      api.stats(),
    ])
    boxes.value = boxRes.boxes
    box.value = boxes.value.find((b) => b.id === props.id) || null
    if (!box.value) {
      toastError('找不到这个盒子')
      router.replace('/treasure')
      return
    }
    if (!countOptions.includes(count.value)) count.value = 10
    recent.value = recRes.records.filter((r) => r.box_id === props.id)
    boxPulls.value = (statsRes.box_stats || []).find((x) => x.box_id === props.id)?.pulls || 0
    document.title = `${box.value.name} · 三国杀盒子模拟器`
  } catch (err) {
    toastError(err.message)
  } finally {
    loading.value = false
  }
}

function switchBox(id) {
  if (id === props.id || opening.value) return
  router.replace(`/box/${id}`)
}

async function open(n) {
  if (!box.value || opening.value) return
  if (affordable.value < n) {
    toastError(`元宝不足，还差 ${(costFor(n) - auth.yuanbao).toLocaleString('zh-CN')}，先去补给吧`)
    return
  }
  opening.value = true
  modalOpen.value = false
  try {
    // 留一点仪式感，不然点完一瞬间弹出 50 张卡太像后台脚本
    const [res] = await Promise.all([
      api.openBox(box.value.id, n),
      new Promise((r) => setTimeout(r, 620)),
    ])
    auth.setYuanbao(res.yuanbao)
    result.value = res
    modalOpen.value = true
    boxPulls.value += n
    await refreshRecent()
  } catch (err) {
    toastError(err.message)
  } finally {
    opening.value = false
  }
}

async function refreshRecent() {
  try {
    const recRes = await api.records(60, { source: 'box', boxId: props.id })
    recent.value = recRes.records.filter((r) => r.box_id === props.id)
  } catch {
    /* 战绩刷新失败不影响主流程 */
  }
}

watch(
  () => props.id,
  () => {
    if (props.id && boxes.value.length && props.id !== box.value?.id) load()
  },
)
onMounted(load)
</script>

<template>
  <div class="shell box-page">
    <!-- 案上开匣：全页底层氛围（战雾 / 四角收墨 / 两枚闲章）。
         固定贴视口 + pointer-events: none，不参与布局，也不挡任何点击。 -->
    <div class="case-field" aria-hidden="true">
      <span class="cf cf--mist"></span>
      <span class="cf cf--vignette"></span>
      <!-- 左：旧竹简侧缘的一道竖向枯笔 -->
      <span class="cf cf--edge-l"></span>
      <!-- 底：横向墨沉积压底（先铺，右侧远山才不会被压掉） -->
      <span class="cf cf--floor"></span>
      <!-- 右：淡墨晕染 + 远山战雾 -->
      <span class="cf cf--edge-r"></span>
      <!-- 右上：一条很淡的残旗 -->
      <span class="cf cf--flag"></span>
      <!-- 右：飞墨小点 -->
      <span class="cf cf--dust"></span>
      <span class="cf cf--seal cf--seal-a">启</span>
      <span class="cf cf--seal cf--seal-b">封</span>
      <span class="cf cf--seal cf--seal-c">鉴</span>
    </div>

    <div class="crumbs">
      <router-link to="/" class="crumb">大厅</router-link>
      <span class="crumb-sep">/</span>
      <router-link to="/treasure" class="crumb">奇珍异宝</router-link>
      <span class="crumb-sep">/</span>
      <span class="crumb crumb--current">{{ box?.name || '开盒' }}</span>
    </div>

    <div v-if="loading" class="empty">正在搬盒子……</div>

    <template v-else-if="box">
      <!-- 仿官方主舞台：左简牍目录 · 中宝匣 · 右立轴 -->
      <section class="stage">
        <!-- 左：竖向竹简目录 -->
        <nav class="box-list" aria-label="礼盒目录">
          <button
            v-for="b in boxes"
            :key="b.id"
            class="box-tab"
            :class="{ 'is-active': b.id === box.id }"
            @click="switchBox(b.id)"
          >
            <span class="box-tab__mark" aria-hidden="true" />
            <span v-if="b.kind !== 'past'" class="box-tab__hot">热卖中</span>
            <b class="box-tab__name">{{ b.name }}</b>
            <i class="box-tab__sub">{{ b.price }} 元宝 · {{ b.kind === 'past' ? '往期复刻' : '在售' }}</i>
          </button>
        </nav>

        <!-- 中：宝匣 + 说明 + 按钮（案上开匣的舞台） -->
        <div class="stage-center">
          <!-- 只做“场”：战雾、戈矛剪影、一束柔和暗聚光 -->
          <div class="top-stage" aria-hidden="true">
            <span class="ts ts--haze"></span>
            <span class="ts ts--spear"></span>
            <!-- 匣子左后方斜向枯墨痕 / 右后方一小片淡墨晕 -->
            <span class="ts ts--blade-l"></span>
            <span class="ts ts--blade-r"></span>
            <span class="ts ts--spot"></span>
            <span class="ts ts--rim"></span>
          </div>

          <div class="stage-top">
            <span class="week-chip">
              本盒累计打开 {{ openedTotal }}
              <i class="seal-stamp seal-stamp--xs week-chip__seal" aria-hidden="true">计</i>
            </span>
          </div>
          <div class="stage-art" :class="{ 'is-opening': opening }">
            <BoxArt :theme="box.theme" :size="252" />
          </div>
          <p class="stage-desc">
            <span>{{ box.subtitle }}</span>
            <i class="seal-stamp seal-stamp--xs" aria-hidden="true">鉴</i>
          </p>

          <div class="stage-actions">
            <button class="open-btn" :disabled="!canOpen" @click="open(1)">
              <span v-if="opening && count === 1" class="spinner" />
              <span class="ink-press" aria-hidden="true" />
              打开一个
            </button>
            <button class="open-btn open-btn--big" :disabled="!canOpenCount || opening" @click="open(count)">
              <span v-if="opening && count > 1" class="spinner" />
              <span class="ink-press" aria-hidden="true" />
              全部打开
              <small>每次最多开{{ maxBulk }}个 · 本次开 {{ count }} 个（{{ costFor(count).toLocaleString('zh-CN') }} 元宝）</small>
            </button>
          </div>

          <div class="stage-extra">
            <div class="chips">
              <button
                v-for="n in countOptions"
                :key="n"
                class="chip"
                :class="{ 'chip--active': count === n }"
                @click="count = n"
              >
                {{ n }} 个
              </button>
            </div>
            <span class="stage-afford">
              当前元宝可开 <b>{{ affordable }}</b> 个
            </span>
          </div>
        </div>

        <!-- 右：稀世珍宝 · 仿古画立轴 -->
        <aside class="stage-right">
          <div v-if="featured" class="prize-stand">
            <div class="scroll">
              <span class="scroll__rod scroll__rod--t" aria-hidden="true" />
              <div class="prize-card">
                <img
                  v-if="featuredArt"
                  :src="featuredArt"
                  :alt="featured.name"
                  :style="{ objectPosition: focusPosition(featured.kind) }"
                  @error="markBroken(featured.name, featured.kind)"
                />
                <span v-else class="prize-card__glyph">{{ featured.name.slice(-2) }}</span>
                <span class="prize-card__rarity" :class="`r-${featured.rarity}`">
                  {{ featured.kind === 'hero' ? '武将' : '皮肤' }}
                </span>
                <span class="prize-card__name">{{ featured.name }}</span>
              </div>
              <span class="scroll__rod scroll__rod--b" aria-hidden="true" />
            </div>
            <span class="prize-banner">稀世珍宝</span>
          </div>
        </aside>
      </section>

      <!-- 详情：简牍 -->
      <section class="panel panel--pad detail-panel">
        <div class="detail-grid">
          <div class="detail-cell">
            <div class="detail-cell__head">
              <h3>
                本盒战绩
                <i class="seal-stamp seal-stamp--xs" aria-hidden="true">录</i>
              </h3>
              <span class="tally">已开 {{ openedTotal }} 个 · 近 {{ Math.min(recent.length, 12) }} 条</span>
            </div>
            <div v-if="!recent.length" class="subtle">暂未开过这个盒子。</div>
            <div v-else class="mini-records">
              <div v-for="r in recent.slice(0, 12)" :key="r.id" class="mini-record">
                <ItemGlyph :name="r.name" :kind="r.kind" :rarity="r.rarity" :size="22" />
                <span class="mini-record__name">{{ r.name }}</span>
                <span class="mini-record__qty">×{{ r.qty }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 概率公示 -->
      <section class="panel panel--pad odds-panel">
        <div class="panel__head">
          <h3>概率公示</h3>
          <span class="subtle">
            权重总和 {{ box.total_weight.toLocaleString('zh-CN') }} ·
            概率 = 物品权重 ÷ 权重总和，与官方公示权重表一致
          </span>
        </div>
        <ProbabilityList :entries="box.entries" :limit="40" />
      </section>
    </template>

    <ResultModal
      :open="modalOpen"
      :data="result"
      :title="`${result?.box_name || ''} · 开盒结果`"
      :loading="opening"
      :again-label="`再开 ${result?.count || 1} 个`"
      @close="modalOpen = false"
      @again="open(result?.count || 1)"
    />
  </div>
</template>

<style scoped>
/* ============================================================
   开盒页 · 案上开匣
   色彩只用全局四色：#1A1714 焦墨 / #2D2720 宣纸 / #9E2B25 朱砂 / #A67C4E 赭石金。
   所有装饰层透明度 ≤8%，印章只做标点，不做墙纸。
   ============================================================ */

.box-page { position: relative; padding-top: 1.8rem; }

/* ------------------------------ 页面底层氛围 ------------------------------ */
.case-field {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  overflow: hidden;
}
.cf { position: absolute; display: block; pointer-events: none; }

/* 中间透气、四周沉墨：让视线自己走到案前 */
.cf--mist {
  inset: 0;
  background:
    radial-gradient(44% 34% at 50% 42%, rgba(166, 124, 78, 0.075), transparent 72%),
    radial-gradient(36% 26% at 18% 14%, rgba(158, 43, 37, 0.042), transparent 74%),
    radial-gradient(50% 30% at 84% 80%, rgba(126, 106, 80, 0.055), transparent 78%);
}
.cf--vignette {
  inset: 0;
  background:
    radial-gradient(36% 26% at 0% 0%, rgba(8, 7, 6, 0.52), transparent 72%),
    radial-gradient(36% 26% at 100% 0%, rgba(8, 7, 6, 0.46), transparent 72%),
    radial-gradient(40% 30% at 0% 100%, rgba(8, 7, 6, 0.58), transparent 74%),
    radial-gradient(40% 30% at 100% 100%, rgba(8, 7, 6, 0.55), transparent 74%);
}
/* 角落两枚极小闲章：启 / 封 */
.cf--seal {
  position: fixed;
  bottom: 3.4vh;
  padding: 3px 4px;
  font-family: var(--font-brush);
  font-size: 12px;
  line-height: 1;
  color: #f0dcbe;
  background: linear-gradient(158deg, #a8322b, #86201b);
  border-radius: 1px;
  box-shadow: inset 0 0 0 1px rgba(240, 220, 190, 0.3);
}
.cf--seal-a { left: 1.6vw; transform: rotate(-5deg); opacity: 0.34; }
.cf--seal-b { right: 1.6vw; transform: rotate(4deg); opacity: 0.27; }
/* 第三枚：只做标点，压在左侧残边中段 */
.cf--seal-c {
  left: clamp(7px, 1.5vw, 24px);
  top: 33%;
  bottom: auto;
  font-size: 10px;
  padding: 2px 3px;
  transform: rotate(-3.5deg);
  opacity: 0.2;
}

/* ---------------- 两侧与底部的「水墨战场纵深」（只在有留白时出现） ---------------- */
/* 左：像从一卷旧录里展开的竹简侧缘——边缘压重 + 几道断续竖飞白 */
.cf--edge-l {
  position: fixed;
  left: 0;
  top: 5vh;
  bottom: 8vh;
  width: clamp(58px, 8.6vw, 126px);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='64' height='720' viewBox='0 0 64 720' preserveAspectRatio='none'%3E%3Cdefs%3E%3ClinearGradient id='eg' x1='0' y1='0' x2='1' y2='0'%3E%3Cstop offset='0' stop-color='%23000000' stop-opacity='.5'/%3E%3Cstop offset='.42' stop-color='%23000000' stop-opacity='.2'/%3E%3Cstop offset='1' stop-color='%23000000' stop-opacity='0'/%3E%3C/linearGradient%3E%3Cfilter id='ef' x='-40%25' y='-4%25' width='180%25' height='108%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.045 0.008' numOctaves='4' seed='17' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='14' xChannelSelector='R' yChannelSelector='G'/%3E%3CfeGaussianBlur stdDeviation='.8'/%3E%3C/filter%3E%3C/defs%3E%3Crect width='64' height='720' fill='url(%23eg)'/%3E%3Cg filter='url(%23ef)' fill='%23d9c6a4'%3E%3Crect x='1.5' y='24' width='7.5' height='196' opacity='.12'/%3E%3Crect x='10' y='96' width='4.5' height='128' opacity='.075'/%3E%3Crect x='2' y='228' width='9' height='84' opacity='.1'/%3E%3Crect x='28' y='238' width='5' height='164' opacity='.045'/%3E%3Crect x='1.6' y='322' width='6' height='238' opacity='.095'/%3E%3Crect x='18' y='398' width='3.6' height='120' opacity='.05'/%3E%3Crect x='2.4' y='572' width='8' height='72' opacity='.105'/%3E%3Crect x='22' y='586' width='4.4' height='116' opacity='.045'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.8;
  -webkit-mask-image: linear-gradient(90deg, #000 0 24%, rgba(0, 0, 0, 0.55) 56%, transparent 100%);
  mask-image: linear-gradient(90deg, #000 0 24%, rgba(0, 0, 0, 0.55) 56%, transparent 100%);
}
/* 右：淡墨晕染 + 远山战雾，把立轴衬成一幅旧画 */
.cf--edge-r {
  position: fixed;
  right: 0;
  top: 2vh;
  bottom: 6vh;
  width: clamp(150px, 17vw, 300px);
  background-image:
    var(--tex-ridge),
    radial-gradient(64% 40% at 66% 44%, rgba(126, 106, 80, 0.2), transparent 80%),
    radial-gradient(50% 38% at 90% 74%, rgba(158, 43, 37, 0.05), transparent 80%);
  background-size: 100% 44%, 100% 100%, 100% 100%;
  background-position: left bottom, 0 0, 0 0;
  background-repeat: no-repeat;
  opacity: 0.8;
  -webkit-mask-image: linear-gradient(270deg, #000 0 38%, rgba(0, 0, 0, 0.58) 74%, transparent 100%);
  mask-image: linear-gradient(270deg, #000 0 38%, rgba(0, 0, 0, 0.58) 74%, transparent 100%);
}
/* 右上：一条很淡的残旗（按 1:1 像素画，避免缩成灰线） */
.cf--flag {
  position: fixed;
  right: clamp(8px, 2.2vw, 42px);
  top: 7vh;
  width: clamp(48px, 5.4vw, 80px);
  height: clamp(140px, 21vh, 232px);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='232' viewBox='0 0 80 232' preserveAspectRatio='none'%3E%3Cg fill='none' stroke='%23e6d6b6' stroke-linecap='round' opacity='.125'%3E%3Cpath d='M62 232 L57 8' stroke-width='2.6'/%3E%3Cpath d='M57 30 C44 25 35 35 25 29 C27 51 25 70 23 92 C36 86 47 94 58 88' stroke-width='2.2'/%3E%3Cpath d='M57 152 C48 149 42 155 36 152' stroke-width='1.8'/%3E%3C/g%3E%3Cg fill='%23e6d6b6' opacity='.07'%3E%3Cpath d='M25 29 L32 36 L27 47 L35 49 L28 61 L23 55 Z'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.85;
  transform: rotate(-1.5deg);
  transform-origin: right bottom;
}
/* 右：4 颗飞墨小点，只是空气里的尘 */
.cf--dust {
  position: fixed;
  right: 1vw;
  top: 26%;
  width: clamp(90px, 11vw, 180px);
  height: 38vh;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='300' viewBox='0 0 160 300' preserveAspectRatio='none'%3E%3Cg fill='%23e6d6b6'%3E%3Ccircle cx='126' cy='30' r='2.4' opacity='.2'/%3E%3Ccircle cx='58' cy='118' r='1.6' opacity='.15'/%3E%3Ccircle cx='142' cy='196' r='2' opacity='.18'/%3E%3Ccircle cx='74' cy='266' r='1.4' opacity='.12'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.75;
}
/* 底：横向墨沉积，下方略暗、上方渐隐，让整页像沉在案几上 */
.cf--floor {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: clamp(140px, 24vh, 280px);
  background-image:
    var(--tex-ridge),
    var(--tex-brush-h),
    linear-gradient(
      to top,
      rgba(8, 7, 5, 0.5) 0%,
      rgba(11, 9, 7, 0.24) 38%,
      rgba(15, 12, 9, 0.06) 72%,
      transparent 100%
    );
  background-size: 100% 46%, 100% 26px, 100% 100%;
  background-position: left bottom, left 34%, 0 0;
  background-repeat: no-repeat;
  opacity: 0.9;
}

/* ------------------------------ 面包屑 ------------------------------ */
.crumbs { display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; margin-bottom: 1.2rem; }
.crumb { color: var(--paper-mute); }
.crumb:hover { color: var(--gold); }
.crumb--current { color: var(--paper-dim); }
.crumb-sep { color: #4d453a; }

/* ------------------------------ 主舞台 ------------------------------ */
.stage {
  position: relative;
  display: grid;
  grid-template-columns: 178px minmax(0, 1fr) 218px;
  gap: 1rem;
  align-items: stretch;
  overflow: hidden;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.26);
  padding: 1.1rem 1.2rem 1.3rem;
  background-color: var(--ink-700);
  background-image:
    radial-gradient(58% 42% at 50% 32%, rgba(166, 124, 78, 0.05), transparent 74%),
    linear-gradient(172deg, rgba(45, 39, 32, 0.94), rgba(20, 17, 14, 0.98));
  box-shadow: inset 0 0 60px -40px rgba(0, 0, 0, 0.9), inset 0 -64px 84px -66px rgba(0, 0, 0, 0.6);
}
.stage::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.06;
  background-image: var(--tex-fiber);
  background-size: 180px 180px;
}
/* 顶边一丝飞白 */
.stage::after {
  content: '';
  position: absolute;
  left: 3%;
  right: 3%;
  top: 0;
  height: 3px;
  background-image: var(--tex-drybrush);
  background-repeat: repeat-x;
  background-size: 240px 16px;
  opacity: 0.28;
  pointer-events: none;
}

/* ------------------------------ ① 左：竖向竹简目录 ------------------------------ */
.box-list {
  position: relative;
  display: grid;
  gap: 0.42rem;
  align-content: start;
  max-height: 560px;
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: rgba(166, 124, 78, 0.42) rgba(0, 0, 0, 0.16);
  /* 顶 / 底一点点墨晕收边 */
  -webkit-mask-image: linear-gradient(180deg, transparent 0, #000 14px, #000 calc(100% - 14px), transparent 100%);
  mask-image: linear-gradient(180deg, transparent 0, #000 14px, #000 calc(100% - 14px), transparent 100%);
}
.box-list::-webkit-scrollbar { width: 5px; }
.box-list::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.18); }
.box-list::-webkit-scrollbar-thumb { background: rgba(166, 124, 78, 0.42); border-radius: 1px; }
.box-list::-webkit-scrollbar-thumb:hover { background: rgba(166, 124, 78, 0.62); }

.box-tab {
  position: relative;
  display: grid;
  gap: 2px;
  padding: 0.5rem 0.62rem 0.52rem 0.8rem;
  border-radius: 2px;
  text-align: left;
  cursor: pointer;
  border: 1px solid rgba(166, 124, 78, 0.16);
  border-left: 1px solid rgba(166, 124, 78, 0.3);
  background-color: var(--ink-700);
  background-image: linear-gradient(180deg, rgba(46, 40, 33, 0.92), rgba(39, 33, 27, 0.96));
  transition: border-color 0.18s;
}
/* 每条的宣纸纤维：5.5%，滚动时不扎眼 */
.box-tab::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: 2px;
  opacity: 0.055;
  background-image: var(--tex-fiber);
  background-size: 130px 130px;
}
/* 只右边缘一点点枯笔飞白 */
.box-tab::after {
  content: '';
  position: absolute;
  right: 0;
  top: 4%;
  bottom: 4%;
  width: 22px;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='26' height='90' viewBox='0 0 26 90'%3E%3Cg fill='%23e6d6b6'%3E%3Crect x='17' y='2' width='2.4' height='15' opacity='.14'/%3E%3Crect x='21' y='20' width='1.4' height='11' opacity='.08'/%3E%3Crect x='16' y='34' width='2' height='18' opacity='.12'/%3E%3Crect x='20' y='57' width='1.6' height='9' opacity='.07'/%3E%3Crect x='16.6' y='69' width='2.2' height='16' opacity='.11'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 26px 90px;
  background-repeat: repeat-y;
  background-position: right top;
  opacity: 0.9;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 72%);
  mask-image: linear-gradient(90deg, transparent, #000 72%);
}
/* 每条错开相位，飞白不至于变成等距刻度 */
.box-tab:nth-child(2n)::after { background-position: right -23px; }
.box-tab:nth-child(3n)::after { background-position: right -57px; }
.box-tab:nth-child(5n)::after { background-position: right -11px; }
/* 选中：左侧一条竖朱砂枯笔，底色几乎不动 */
.box-tab__mark {
  position: absolute;
  left: 1px;
  top: 13%;
  bottom: 13%;
  width: 3px;
  opacity: 0;
  background: linear-gradient(180deg, transparent, var(--crimson) 16%, var(--crimson) 82%, rgba(158, 43, 37, 0.16));
  transition: opacity 0.2s;
  -webkit-mask-image: repeating-linear-gradient(
    180deg,
    #000 0 5px, rgba(0, 0, 0, 0.26) 5px 6px,
    #000 6px 12px, rgba(0, 0, 0, 0.58) 12px 13px,
    #000 13px 21px
  );
  mask-image: repeating-linear-gradient(
    180deg,
    #000 0 5px, rgba(0, 0, 0, 0.26) 5px 6px,
    #000 6px 12px, rgba(0, 0, 0, 0.58) 12px 13px,
    #000 13px 21px
  );
}
.box-tab.is-active .box-tab__mark { opacity: 0.95; }
.box-tab__name {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: 0.86rem;
  letter-spacing: 0.06em;
  color: #dfceaa;
  transition: color 0.18s;
}
.box-tab__sub { font-family: var(--font-sans); font-style: normal; font-size: 0.64rem; color: #8c7c5f; }
.box-tab.is-active {
  border-color: rgba(166, 124, 78, 0.3);
  border-left-color: rgba(166, 124, 78, 0.42);
  background-image: linear-gradient(180deg, rgba(56, 47, 38, 0.96), rgba(41, 35, 28, 0.98));
}
.box-tab.is-active .box-tab__name { color: var(--gold-2); }
.box-tab.is-active .box-tab__sub { color: #9c8b6d; }
/* 「热卖中」＝ 朱砂篆刻方印，不再是红底标签 */
.box-tab__hot {
  position: absolute;
  top: -6px;
  right: -4px;
  z-index: 3;
  padding: 2px 4px;
  font-family: var(--font-brush);
  font-size: 0.56rem;
  line-height: 1.1;
  letter-spacing: 0.02em;
  white-space: nowrap;
  color: #f6e7cc;
  background: linear-gradient(160deg, #a8322b, #86201b);
  border-radius: 1px;
  box-shadow: inset 0 0 0 1px rgba(246, 231, 204, 0.3);
  transform: rotate(-3deg);
  opacity: 0.92;
}

/* ------------------------------ ③ 中：案上开匣 ------------------------------ */
.stage-center {
  position: relative;
  display: grid;
  justify-items: center;
  align-content: start;
  gap: 0.5rem;
  isolation: isolate;
}
/* 整层往边缘淡出：否则径向压暗会在中栏边界切出一条硬边 */
.top-stage {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
.ts { position: absolute; display: block; pointer-events: none; }
/* 战雾：极淡，只让空处不死黑 */
.ts--haze {
  inset: 0;
  background:
    radial-gradient(52% 38% at 26% 22%, rgba(126, 106, 80, 0.07), transparent 76%),
    radial-gradient(46% 34% at 78% 66%, rgba(158, 43, 37, 0.045), transparent 78%);
}
/* 匣子左后方：一条斜向枯墨痕，中心不动它 */
.ts--blade-l {
  left: 0;
  top: 17%;
  width: 38%;
  height: 40%;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='150' viewBox='0 0 240 150' preserveAspectRatio='none'%3E%3Cdefs%3E%3Cfilter id='bl' x='-20%25' y='-60%25' width='140%25' height='220%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.03 0.09' numOctaves='3' seed='5' result='t'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='t' scale='4' xChannelSelector='R' yChannelSelector='G'/%3E%3CfeGaussianBlur stdDeviation='.5'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23bl)' stroke='%23e6d6b6' fill='none' stroke-linecap='butt'%3E%3Cpath d='M6 98 C 44 90 82 80 124 67' stroke-width='3.6' opacity='.062'/%3E%3Cpath d='M130 64 C 152 58 170 54 188 49' stroke-width='2.4' opacity='.046'/%3E%3Cpath d='M194 47 C 206 44 216 41 228 37' stroke-width='1.6' opacity='.034'/%3E%3Cpath d='M16 108 C 46 102 70 95 98 87' stroke-width='1.5' opacity='.03'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  opacity: 0.8;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 22%, #000 68%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 22%, #000 68%, transparent);
}
/* 匣子右后方：一小片淡墨晕 */
.ts--blade-r {
  right: 0;
  top: 23%;
  width: 32%;
  height: 44%;
  background: radial-gradient(62% 52% at 58% 44%, rgba(206, 190, 158, 0.1), transparent 76%);
}
/* 隐约戈矛剪影：4–5%，只露枪杆与一点锋，不画人 */
.ts--spear {
  inset: 0;
  opacity: 0.62;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='520' height='560' viewBox='0 0 520 560' preserveAspectRatio='none'%3E%3Cdefs%3E%3Cfilter id='sb' x='-25%25' y='-6%25' width='150%25' height='112%25'%3E%3CfeGaussianBlur stdDeviation='1.5'/%3E%3C/filter%3E%3C/defs%3E%3Cg filter='url(%23sb)'%3E%3Cg stroke='%23e6d6b6' fill='none' stroke-linecap='round'%3E%3Cpath d='M62 560 L84 150' stroke-width='3.2' opacity='.1'/%3E%3Cpath d='M84 150 L78 106' stroke-width='2.4' opacity='.09'/%3E%3Cpath d='M116 560 L132 306' stroke-width='2.2' opacity='.055'/%3E%3Cpath d='M456 560 L434 194' stroke-width='3' opacity='.085'/%3E%3Cpath d='M434 194 L428 158' stroke-width='2.2' opacity='.075'/%3E%3C/g%3E%3Cg fill='%23e6d6b6'%3E%3Cpath d='M78 106 L90 122 L99 104 L86 150 Z' opacity='.075'/%3E%3Cpath d='M428 158 L440 172 L448 156 L436 194 Z' opacity='.065'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
  -webkit-mask-image: radial-gradient(72% 62% at 50% 48%, #000 18%, transparent 84%);
  mask-image: radial-gradient(72% 62% at 50% 48%, #000 18%, transparent 84%);
}
/* 一束柔和暗聚光：只是把视线轻轻锁在匣子上 */
.ts--spot {
  inset: 0;
  background: radial-gradient(
    44% 36% at 50% 40%,
    rgba(236, 226, 202, 0.085) 0%,
    rgba(236, 226, 202, 0.032) 46%,
    transparent 72%
  );
}
/* 四周缓缓沉向焦墨 */
.ts--rim {
  inset: 0;
  background: radial-gradient(66% 56% at 50% 40%, transparent 42%, rgba(10, 8, 6, 0.5) 100%);
  /* 软边收到中栏以内，避免在栏边界切出直边 */
  -webkit-mask-image: radial-gradient(48% 50% at 50% 40%, #000 30%, transparent 100%);
  mask-image: radial-gradient(48% 50% at 50% 40%, #000 30%, transparent 100%);
}

.stage-top, .stage-art, .stage-desc, .stage-actions, .stage-extra { position: relative; z-index: 1; }
.stage-top { align-self: flex-start; }

/* ② 小古幡横签 */
.week-chip {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 3px 24px 3px 12px;
  font-family: var(--font-sans);
  font-size: 0.71rem;
  letter-spacing: 0.1em;
  color: var(--gold-2);
  background: linear-gradient(180deg, rgba(214, 198, 161, 0.1), rgba(214, 198, 161, 0.032));
  border-radius: 1px;
}
.week-chip::before,
.week-chip::after {
  content: '';
  position: absolute;
  left: 2%;
  right: 2%;
  height: 2px;
  pointer-events: none;
  background-image: var(--tex-drybrush);
  background-repeat: repeat-x;
  background-size: 240px 16px;
  opacity: 0.32;
}
.week-chip::before { top: 0; }
.week-chip::after { bottom: 0; }
.week-chip__seal {
  position: absolute;
  right: 3px;
  top: 50%;
  transform: translateY(-50%) rotate(-4deg);
}

.stage-art { display: grid; place-items: center; margin-top: 0.35rem; }
.stage-art :deep(svg) {
  animation: caseBreath 7s ease-in-out infinite;
  filter: drop-shadow(0 20px 24px rgba(0, 0, 0, 0.52));
}
.stage-art.is-opening :deep(svg) { animation: shakeBox 0.42s ease-in-out infinite; }
/* 静置只微呼吸：7 秒一个来回，位移 3.6px */
@keyframes caseBreath {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3.6px); }
}
@keyframes shakeBox {
  0%, 100% { transform: rotate(-2.2deg) translateY(0) scale(1); }
  50% { transform: rotate(2.6deg) translateY(-5px) scale(1.03); }
}

.stage-desc {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  margin: 0.5rem 0 0.45rem;
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.09em;
  color: var(--gold-2);
  text-align: center;
}

/* 战旗朱砂主按钮 */
.stage-actions { display: flex; align-items: stretch; gap: 0.85rem; margin-top: 0.4rem; }
.open-btn {
  position: relative;
  display: grid;
  justify-items: center;
  gap: 2px;
  min-width: 158px;
  padding: 0.54rem 1.3rem 0.58rem;
  overflow: hidden;
  isolation: isolate;
  border: 1px solid rgba(158, 43, 37, 0.85);
  border-radius: 1px;
  background-color: var(--crimson);
  background-image: linear-gradient(178deg, #a8322b 0%, #9e2b25 52%, #7d1d19 100%);
  box-shadow: inset 0 1px 0 rgba(255, 236, 210, 0.14), 0 10px 20px -16px #000;
  font-family: var(--font-sans);
  font-weight: 700;
  font-size: 0.98rem;
  letter-spacing: 0.2em;
  color: #fdf2dd;
  cursor: pointer;
  transition: filter 0.18s, transform 0.18s, box-shadow 0.18s;
}
/* 极微弱旧织物肌理 5% */
.open-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.05;
  background-image: var(--tex-fiber);
  background-size: 140px 140px;
}
/* hover：干笔横扫 */
.open-btn::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 70%;
  z-index: 2;
  pointer-events: none;
  background-image: var(--tex-drybrush);
  background-repeat: repeat-x;
  background-position: center;
  background-size: 240px 16px;
  opacity: 0;
  transform: translateX(-70%);
}
.open-btn:hover:not(:disabled) { filter: brightness(1.06); transform: translateY(-1px); }
.open-btn:hover:not(:disabled)::after { animation: brushSweep 0.44s ease-out both; }
.open-btn:active:not(:disabled) { transform: translateY(0); box-shadow: inset 0 2px 8px rgba(20, 14, 10, 0.4); }
.open-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.open-btn--big {
  min-width: 214px;
  font-size: 0.96rem;
  letter-spacing: 0.16em;
  outline: 1px solid rgba(166, 124, 78, 0.46);
  outline-offset: 3px;
}
.open-btn small {
  font-family: var(--font-sans);
  font-weight: 400;
  font-size: 0.58rem;
  letter-spacing: 0.02em;
  color: rgba(253, 242, 221, 0.7);
}
/* 点击：小墨滴洇开 */
.ink-press {
  position: absolute;
  left: 50%;
  top: 50%;
  z-index: 1;
  width: 130%;
  aspect-ratio: 1;
  transform: translate(-50%, -50%) scale(0.32);
  border-radius: 50%;
  opacity: 0;
  pointer-events: none;
  background: radial-gradient(circle, rgba(10, 7, 5, 0.5) 0 36%, rgba(10, 7, 5, 0.22) 60%, transparent 72%);
  transition: transform 0.55s cubic-bezier(0.2, 0.8, 0.3, 1), opacity 0.55s ease;
}
.open-btn:active:not(:disabled) .ink-press {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1);
  transition: transform 0.14s ease-out, opacity 0.06s;
}

/* 数量：迷你竹简小方钮 */
.stage-extra { display: flex; align-items: center; gap: 0.7rem; margin-top: 0.5rem; }
.chips { display: flex; gap: 0.3rem; }
.stage-extra .chip {
  min-width: 46px;
  padding: 0.26rem 0.5rem;
  border-radius: 1px;
  border: 1px solid rgba(166, 124, 78, 0.2);
  border-top-color: rgba(166, 124, 78, 0.34);
  background-image: linear-gradient(180deg, rgba(56, 48, 39, 0.9), rgba(33, 28, 23, 0.95));
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.02em;
  color: var(--paper-dim);
  cursor: pointer;
  transition: color 0.16s, border-color 0.16s;
}
.stage-extra .chip:hover { color: var(--paper); border-color: rgba(166, 124, 78, 0.5); }
.stage-extra .chip--active {
  color: #241a0e;
  font-weight: 700;
  border-color: rgba(240, 224, 194, 0.4);
  background-image: linear-gradient(180deg, #c69a66, #a67c4e 62%, #8a6438);
  box-shadow: inset 0 1px 0 rgba(255, 244, 220, 0.22);
}
.stage-afford { font-family: var(--font-sans); font-size: 0.72rem; color: #8f8069; }
.stage-afford b { font-weight: 600; color: #bda98a; font-variant-numeric: tabular-nums; }

/* ------------------------------ ④ 右：稀世珍宝 · 立轴 ------------------------------ */
.stage-right { display: grid; align-content: start; justify-items: center; }
.prize-stand {
  display: grid;
  grid-template-columns: auto auto;
  grid-template-rows: auto;
  gap: 0.4rem 0.5rem;
  align-items: start;
  justify-content: center;
}
.scroll {
  grid-column: 1;
  grid-row: 1;
  position: relative;
  padding: 7px 5px;
  background: linear-gradient(180deg, rgba(226, 214, 186, 0.07), rgba(226, 214, 186, 0.015));
}
.scroll::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.06;
  background-image: var(--tex-fiber);
  background-size: 120px 120px;
}
.scroll__rod {
  position: absolute;
  left: -4px;
  right: -4px;
  height: 4px;
  border-radius: 1px;
  background: linear-gradient(180deg, #7d6340, #4a3823 66%, #2b1f14);
  box-shadow: inset 0 1px 0 rgba(201, 164, 110, 0.28), 0 1px 2px rgba(0, 0, 0, 0.5);
}
.scroll__rod--t { top: 0; }
.scroll__rod--b { bottom: 0; left: -7px; right: -7px; height: 6px; }
/* 轴头：极小两个挡头，不抢画心 */
.scroll__rod--b::before,
.scroll__rod--b::after {
  content: '';
  position: absolute;
  top: -2px;
  width: 4px;
  height: 10px;
  border-radius: 1px;
  background: linear-gradient(180deg, #8a6b45, #3c2c1b);
}
.scroll__rod--b::before { left: -1px; }
.scroll__rod--b::after { right: -1px; }

.prize-card {
  position: relative;
  width: 132px;
  aspect-ratio: 3 / 4.2;
  overflow: hidden;
  background: #1a1714;
  box-shadow: 0 12px 24px -16px #000;
}
.prize-card img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.prize-card__glyph {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-family: var(--font-brush);
  font-size: 1.6rem;
  color: var(--gold-2);
}
/* 底部压暗，只压到能看清名字为止 */
.prize-card::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 2;
  background: linear-gradient(180deg, transparent 58%, rgba(10, 8, 5, 0.86));
}
/* 画心四周一圈绫绢衬边 */
.prize-card::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border: 4px solid rgba(206, 191, 158, 0.9);
  box-shadow: inset 0 0 0 1px rgba(166, 124, 78, 0.42);
}
.prize-card__rarity {
  position: absolute;
  z-index: 4;
  top: 9px;
  left: 9px;
  padding: 1px 5px;
  border-radius: 1px;
  font-size: 0.6rem;
  color: #241a0e;
  background: linear-gradient(160deg, #c69a66, #a67c4e);
}
.prize-card__name {
  position: absolute;
  z-index: 4;
  left: 10px;
  right: 10px;
  bottom: 9px;
  font-size: 0.72rem;
  color: #f8ecd0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 竖排题签 */
.prize-banner {
  grid-column: 2;
  grid-row: 1;
  writing-mode: vertical-rl;
  margin-top: 4px;
  padding: 8px 3px 10px;
  font-family: var(--font-brush);
  font-size: 1rem;
  line-height: 1.1;
  letter-spacing: 0.22em;
  text-align: center;
  color: #e8d6b0;
  background: linear-gradient(180deg, rgba(236, 226, 202, 0.07), rgba(236, 226, 202, 0.015));
  border-left: 1px solid rgba(166, 124, 78, 0.28);
  border-right: 1px solid rgba(166, 124, 78, 0.28);
}
/* ------------------------------ ⑤ 底部：简牍（只留战绩） ------------------------------ */
.detail-panel { margin-top: 1.1rem; }
.detail-grid { display: grid; grid-template-columns: 1fr; gap: 1.6rem; }
.detail-cell { position: relative; }
/* 分割线：一段短枯笔，不是直线 */
.detail-cell + .detail-cell::before {
  content: '';
  position: absolute;
  left: -0.8rem;
  top: 14%;
  bottom: 14%;
  width: 6px;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='6' height='120' viewBox='0 0 6 120' preserveAspectRatio='none'%3E%3Cg fill='%23e6d6b6'%3E%3Crect x='1.6' y='0' width='2.2' height='26' opacity='.16'/%3E%3Crect x='2' y='30' width='1.6' height='18' opacity='.1'/%3E%3Crect x='1.2' y='52' width='2.6' height='34' opacity='.18'/%3E%3Crect x='2.2' y='90' width='1.4' height='14' opacity='.08'/%3E%3Crect x='1.6' y='108' width='2' height='12' opacity='.12'/%3E%3C/g%3E%3C/svg%3E");
  background-size: 100% 100%;
  background-repeat: no-repeat;
}
.detail-cell__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}
.detail-cell__head h3 {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-family: var(--font-display);
  font-weight: 400;
  font-size: 0.98rem;
  color: var(--paper);
}
.tally {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.03em;
  color: var(--gold-2);
  font-variant-numeric: tabular-nums;
}
.mini-records {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 0.32rem 2.2rem;
}
.mini-record { display: flex; align-items: center; gap: 0.45rem; padding-right: 0.5rem; font-size: 0.76rem; }
.mini-record__name { color: var(--paper-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mini-record__qty { margin-left: auto; color: var(--paper-mute); font-variant-numeric: tabular-nums; }
.odds-panel { margin-top: 1.1rem; }

/* ------------------------------ 响应式 ------------------------------ */
@media (max-width: 1060px) {
  .stage { grid-template-columns: 1fr; }
  .box-list {
    grid-template-columns: repeat(3, 1fr);
    max-height: 320px;
    -webkit-mask-image: none;
    mask-image: none;
  }
  /* 网格化后角标再往外飘会压到上一张卡片：收进卡片右下角 */
  .box-tab__hot { top: auto; bottom: 5px; right: 6px; }
  .prize-stand { margin-top: 0.6rem; }
  .detail-grid { grid-template-columns: 1fr; }
  .detail-cell + .detail-cell::before { display: none; }
  .cf--seal { display: none; }
  .ts--spear { background-size: 78% 100%; background-position: center; }
}
@media (max-width: 620px) {
  .box-list { grid-template-columns: repeat(2, 1fr); }
  .stage-actions { flex-direction: column; width: 100%; }
  .open-btn, .open-btn--big { width: 100%; min-width: 0; }
  .stage-extra { flex-direction: column; gap: 0.5rem; }
  .chips { flex-wrap: wrap; justify-content: center; }
  .prize-card { width: 118px; }
  .ts--spear { opacity: 0.4; }
}
/* 留白不够时（窄屏左右贴边）收掉两侧气氛层，避免挤到舞台 */
@media (max-width: 1280px) {
  .cf--edge-r, .cf--flag, .cf--dust { display: none; }
}
@media (max-width: 900px) {
  .cf--edge-l { width: 34px; opacity: 0.2; }
  .cf--seal-c { display: none; }
  .cf--floor { height: 120px; opacity: 0.7; }
}

@media (prefers-reduced-motion: reduce) {
  .stage-art :deep(svg) { animation: none; }
  .open-btn:hover:not(:disabled)::after { animation: none; }
  .ink-press { display: none; }
}
</style>
