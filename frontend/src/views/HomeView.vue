<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ItemGlyph from '../components/ItemGlyph.vue'
import { playInkBurst } from '../composables/useInkBurst'
import { useToast } from '../composables/useToast'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const { error: toastError } = useToast()

const inventory = ref({ items: [], heroes: [], skins: [] })
const records = ref([])

// 盒子模拟器大厅的三个玩法入口；抽盒子的功能已收进「奇珍异宝」
const entries = [
  {
    to: '/treasure',
    title: '奇珍异宝',
    en: 'TREASURE PAVILION',
    glyph: '珍',
    cta: '开始抽取',
    desc: '礼盒、权重、附赠都摆在这里。想验证手气，从这里进。',
    locked: false,
    burst: true, // 三处玩法入口统一带泼墨转场
  },
  {
    to: '/corridor',
    title: '梦之回廊',
    en: 'CORRIDOR OF DREAMS',
    glyph: '梦',
    cta: '进入',
    desc: '迷迭珠换记忆碎片，横竖斜连成 12 条线，集齐 25 种碎片拿本期传说动皮。',
    locked: false,
    burst: true,
  },
  {
    to: '/palace',
    title: '天宫宝库',
    en: 'CELESTIAL VAULT',
    glyph: '宫',
    cta: '进入',
    desc: '天工石开库，12 格奖池里摆着 3 名武将、3 款皮肤；幸运值满 200 必中大奖。',
    locked: false,
    burst: true,
  },
]

const itemCount = (name) =>
  inventory.value.items.filter((i) => i.name === name).reduce((s, i) => s + i.qty, 0)

const recruitCards = [
  {
    pool: 'hero',
    title: '武将招募',
    costName: '招募令',
    desc: '217 位武将，分普通 / 精品 / 史诗三档',
  },
  {
    pool: 'skin',
    title: '皮肤收集',
    costName: '雁翎甲',
    desc: '543 款皮肤，按收集分级逐级解锁',
  },
]

const rareRecord = (r) => ['legendary', 'epic'].includes(r.rarity)

/* ------------------------------ 浮尘墨点 ------------------------------
   用固定种子生成，位置稳定不跳动；动画极轻，只做「尘土缓慢上浮」 */
function seeded(seed) {
  let s = seed
  return () => {
    s = (s * 1103515245 + 12345) % 2147483648
    return s / 2147483648
  }
}
const rnd = seeded(20261021)
const DUST = Array.from({ length: 18 }, () => {
  const size = 1.2 + rnd() * 3.4
  return {
    left: `${(rnd() * 100).toFixed(2)}%`,
    top: `${(8 + rnd() * 88).toFixed(2)}%`,
    width: `${size.toFixed(2)}px`,
    height: `${size.toFixed(2)}px`,
    '--drift': `${(18 + rnd() * 26).toFixed(1)}s`,
    '--delay': `${(-rnd() * 30).toFixed(1)}s`,
    '--dx': `${(rnd() * 30 - 15).toFixed(1)}px`,
    '--dy': `${(-22 - rnd() * 40).toFixed(1)}px`,
    '--peak': (0.05 + rnd() * 0.1).toFixed(2),
  }
})

/* ------------------------------ 入口点击 ------------------------------ */
function onEntryClick(entry, ev, navigate) {
  const plain = !ev.metaKey && !ev.ctrlKey && !ev.shiftKey && !ev.altKey && ev.button === 0
  if (entry.burst && plain) {
    ev.preventDefault()
    playInkBurst(router, entry.to, ev)
    return
  }
  navigate(ev)
}

onMounted(async () => {
  try {
    const [invRes, recRes] = await Promise.all([api.inventory(), api.records(8)])
    inventory.value = invRes
    records.value = recRes.records
  } catch (err) {
    toastError(err.message)
  }
})
</script>

<template>
  <div class="home">
    <!-- 供 HTML 元素引用的粗糙边缘滤镜（印章、笔触外框） -->
    <svg class="home__defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <filter id="inkEdge" x="-14%" y="-16%" width="128%" height="132%">
          <feTurbulence type="fractalNoise" baseFrequency="0.013 0.021" numOctaves="3" seed="5" result="t" />
          <feDisplacementMap in="SourceGraphic" in2="t" scale="2.6" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="sealEdge" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.09" numOctaves="2" seed="3" result="t" />
          <feDisplacementMap in="SourceGraphic" in2="t" scale="2.2" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>
    </svg>

    <!-- 战场水墨：固定的屏风层，浓墨压四边，中间大片留白 -->
    <div class="home__scene" aria-hidden="true">
      <svg class="home__art" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <defs>
          <filter id="artSoft" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="16" />
          </filter>
          <filter id="artRough" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.026" numOctaves="3" seed="11" result="t" />
            <feDisplacementMap in="SourceGraphic" in2="t" scale="8" xChannelSelector="R" yChannelSelector="G" />
          </filter>
          <radialGradient id="artCorner" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#241e17" stop-opacity="0.42" />
            <stop offset="70%" stop-color="#241e17" stop-opacity="0.17" />
            <stop offset="100%" stop-color="#241e17" stop-opacity="0" />
          </radialGradient>
        </defs>

        <!-- 角落墨渍 -->
        <g>
          <ellipse cx="40" cy="30" rx="230" ry="180" fill="url(#artCorner)" />
          <ellipse cx="1410" cy="-10" rx="200" ry="150" fill="url(#artCorner)" />
          <ellipse cx="70" cy="880" rx="280" ry="200" fill="url(#artCorner)" />
          <ellipse cx="1400" cy="890" rx="260" ry="170" fill="url(#artCorner)" />
        </g>

        <!-- 远处朦胧战山（淡墨晕开） -->
        <g filter="url(#artSoft)">
          <path d="M860 700 L980 552 L1050 610 L1140 480 L1230 600 L1310 534 L1440 660 L1440 900 L860 900 Z"
                fill="#4a4033" opacity="0.34" />
          <path d="M980 900 L1090 690 L1170 772 L1250 648 L1360 780 L1440 706 L1440 900 Z"
                fill="#332b22" opacity="0.32" />
          <path d="M0 640 L110 520 L190 580 L280 494 L360 566 L440 528 L520 640 L520 900 L0 900 Z"
                fill="#453b2e" opacity="0.24" />
        </g>

        <!-- 硝烟（提白，制造雾气与留白） -->
        <g filter="url(#artSoft)">
          <ellipse cx="905" cy="196" rx="250" ry="74" fill="#f4ecdc" opacity="0.42" />
          <ellipse cx="1090" cy="132" rx="180" ry="54" fill="#f7f0e1" opacity="0.3" />
          <ellipse cx="710" cy="252" rx="196" ry="50" fill="#f1e8d6" opacity="0.22" />
          <ellipse cx="1240" cy="330" rx="150" ry="44" fill="#f4ecdc" opacity="0.2" />
        </g>

        <!-- 干裂黄土：只在四边起纹，绝不压中间 -->
        <g fill="none" stroke="#63543f" stroke-width="1.2" stroke-linecap="round"
           opacity="0.42" filter="url(#artRough)">
          <path d="M-10 706 q74 22 122 -10 t96 -4 q54 14 92 -18" />
          <path d="M30 792 q92 8 142 -26 t122 6" />
          <path d="M110 860 q60 -40 132 -30 t118 -34" />
          <path d="M1150 742 q80 20 132 -12 t132 8" />
          <path d="M1250 828 q70 -14 112 -40 t92 12" />
          <path d="M1330 660 q40 30 96 24" />
          <path d="M250 620 q66 -18 104 8" />
        </g>
      </svg>

      <!-- 左上：残破军旗 -->
      <svg class="deco deco--banner" viewBox="0 0 300 380">
        <defs>
          <filter id="bannerRough" x="-18%" y="-14%" width="136%" height="128%">
            <feTurbulence type="fractalNoise" baseFrequency="0.022" numOctaves="2" seed="7" result="t" />
            <feDisplacementMap in="SourceGraphic" in2="t" scale="3.4" xChannelSelector="R" yChannelSelector="G" />
          </filter>
          <filter id="bannerSoft" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="14" />
          </filter>
          <mask id="bannerTatter">
            <rect width="300" height="380" fill="#fff" />
            <path d="M112 92 q7 20 3 44 q-9 -3 -9 -22 q0 -16 6 -22 z" fill="#000" />
            <path d="M160 66 q6 26 2 52 q-8 -4 -8 -26 q0 -18 6 -26 z" fill="#000" />
          </mask>
        </defs>

        <ellipse cx="140" cy="170" rx="122" ry="150" fill="#2a231b" opacity="0.1" filter="url(#bannerSoft)" />

        <g filter="url(#bannerRough)">
          <!-- 旗杆与横杆 -->
          <path d="M42 6 L52 8 L62 372 L52 374 Z" fill="#141110" opacity="0.7" />
          <path d="M40 40 L206 26 L207 36 L41 50 Z" fill="#141110" opacity="0.62" />
          <!-- 旗面：从横杆垂下，下缘撕成宽窄不一、长短不齐的布条 -->
          <path
            d="M50 48 L202 36 L206 190
               C200 226 198 250 193 282
               C189 244 186 214 184 196
               Q178 232 171 250
               Q167 214 163 194
               C159 228 152 252 146 266
               C142 234 138 206 134 192
               Q126 228 118 244
               Q116 212 112 194
               C106 228 98 250 90 260
               C86 228 82 204 78 190
               Q70 216 62 228
               Q58 202 54 188 Z"
            fill="#141110" opacity="0.62" mask="url(#bannerTatter)" />
          <!-- 墨色不匀 -->
          <g fill="#dbcbb0" opacity="0.2" filter="url(#bannerSoft)">
            <path d="M66 66 q30 -10 40 14 q-4 30 -34 26 q-16 -20 -6 -40 z" />
            <path d="M150 58 q24 6 20 34 q-22 14 -32 -4 q-2 -22 12 -30 z" />
          </g>
          <!-- 布褶 -->
          <path d="M96 56 L92 214 M148 50 L146 232" stroke="#e6dbc4" stroke-width="2.4" opacity="0.32" fill="none" />
          <!-- 杆顶矛尖 -->
          <path d="M44 -14 L47 12 L57 9 Z" fill="#141110" opacity="0.7" />
        </g>
      </svg>

      <!-- 左下：半隐的铁戟与刀盾 -->
      <svg class="deco deco--halberd" viewBox="0 0 380 320">
        <defs>
          <filter id="halberdRough" x="-16%" y="-16%" width="132%" height="132%">
            <feTurbulence type="fractalNoise" baseFrequency="0.024" numOctaves="2" seed="19" result="t" />
            <feDisplacementMap in="SourceGraphic" in2="t" scale="3.6" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </defs>
        <g filter="url(#halberdRough)">
          <!-- 长杆 -->
          <path d="M118 320 L204 36 L215 38 L134 320 Z" fill="#171310" opacity="0.42" />
          <!-- 月牙戟刃 -->
          <path d="M204 36 q36 -8 56 14 q-32 4 -36 36 q-20 -8 -32 -26 z" fill="#171310" opacity="0.46" />
          <!-- 侧枝刺 -->
          <path d="M213 100 q32 -10 50 8 q-34 2 -44 24 z" fill="#171310" opacity="0.36" />
          <!-- 刀盾：被左边缘裁去一半 -->
          <path d="M-46 172 q76 -36 132 -6 l6 68 q-66 60 -144 46 z" fill="#171310" opacity="0.36" />
          <path d="M-14 208 q40 -16 72 -2 M-10 232 q40 -14 70 -2" stroke="#ddd2ba" stroke-width="2"
                opacity="0.45" fill="none" />
          <!-- 断矛 -->
          <path d="M-12 270 L184 216 L186 223 L-10 278 Z" fill="#171310" opacity="0.38" />
          <path d="M198 252 L284 216 L286 223 L200 259 Z" fill="#171310" opacity="0.32" />
          <path d="M184 216 l18 -7 l-3 13 z" fill="#171310" opacity="0.38" />
          <!-- 碎石 -->
          <g fill="#171310" opacity="0.26">
            <ellipse cx="244" cy="294" rx="27" ry="11" />
            <ellipse cx="304" cy="278" rx="16" ry="8" />
            <ellipse cx="332" cy="304" rx="34" ry="12" />
            <ellipse cx="192" cy="308" rx="15" ry="7" />
          </g>
        </g>
      </svg>

      <!-- 右下：干枯草叶 -->
      <svg class="deco deco--grass" viewBox="0 0 320 260">
        <defs>
          <filter id="grassRough" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="29" result="t" />
            <feDisplacementMap in="SourceGraphic" in2="t" scale="2.8" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </defs>
        <g filter="url(#grassRough)" fill="#171310" opacity="0.34">
          <path d="M252 260 q-24 -76 -78 -130 q36 64 62 132 z" />
          <path d="M268 260 q-6 -88 -46 -156 q20 76 32 158 z" />
          <path d="M234 260 q-46 -62 -108 -94 q58 46 92 98 z" />
          <path d="M214 260 q-60 -36 -122 -46 q66 22 110 52 z" />
          <path d="M284 260 q16 -72 34 -100 q-8 46 -18 102 z" />
          <path d="M196 260 q-30 -46 -66 -66 q34 30 52 68 z" />
        </g>
        <g fill="#171310" opacity="0.2">
          <ellipse cx="286" cy="252" rx="22" ry="6" />
          <ellipse cx="214" cy="256" rx="18" ry="5" />
        </g>
      </svg>

      <!-- 极淡浮尘 -->
      <div class="home__dust">
        <span v-for="(d, i) in DUST" :key="i" class="dust" :style="d" />
      </div>

      <!-- 远处地平线：一层压地的淡墨，把两侧的残兵沉进战场 -->
      <div class="home__ground" />
    </div>

    <div class="home__grain" aria-hidden="true" />
    <div class="home__veil" aria-hidden="true" />
    <!-- 纸的上缘：从顶栏撕下来的一道墨边 -->
    <svg class="home__edge" viewBox="0 0 1440 40" preserveAspectRatio="none" aria-hidden="true">
      <path
        d="M0 0 H1440 V20 q-62 14 -126 4 q-72 -10 -134 8 q-84 16 -152 -4 q-92 -20 -172 6 q-72 18 -142 -4 q-82 -26 -162 4 q-72 20 -142 -2 q-84 -24 -162 8 q-72 22 -148 -4 Z"
        fill="#0b0a09" />
    </svg>

    <div class="shell home__inner">
      <section class="home-head">
        <p class="home-head__eyebrow">大厅 · LOBBY</p>

        <div class="home-title-row">
          <h1 class="home-title">三国杀抽盒模拟器</h1>
          <span class="home-seal" aria-hidden="true">
            <span>乱</span><span>世</span><span>争</span><span>锋</span>
          </span>
        </div>

        <p class="home-head__greet">
          {{ auth.user?.nickname || '杀友' }}，今日可敢开盒？
        </p>
        <p class="home-head__meta">
          当前元宝 <b>{{ auth.yuanbao.toLocaleString('zh-CN') }}</b>
          ，够开 <b>{{ Math.floor(auth.yuanbao / 100) }}</b> 个半价盒。概率就在那儿，不看也不会变。
        </p>
      </section>

      <section class="entries">
        <div class="entries__head">
          <h2>三处战场</h2>
          <span class="entries__note">择一处入局</span>
        </div>

        <div class="entries__grid">
          <router-link
            v-for="(e, i) in entries"
            :key="e.to"
            v-slot="{ href, navigate }"
            :to="e.to"
            custom
          >
            <a
              :href="href"
              class="entry"
              :class="{ 'entry--primary': i === 0, 'entry--locked': e.locked }"
              @click="onEntryClick(e, $event, navigate)"
            >
              <span class="entry__glyph" aria-hidden="true">{{ e.glyph }}</span>
              <span class="entry__frame" aria-hidden="true" />
              <div class="entry__top">
                <h3>{{ e.title }}</h3>
              </div>
              <p class="entry__en">{{ e.en }}</p>
              <p class="entry__desc">{{ e.desc }}</p>
              <span class="entry__go">
                {{ e.locked ? '看看门牌' : e.cta }}
                <span class="entry__arrow" aria-hidden="true">→</span>
              </span>
            </a>
          </router-link>
        </div>
      </section>

      <section class="home-lower">
        <div class="panel panel--pad recruit-block">
          <div class="panel__head">
            <h3>招募与皮肤收集</h3>
          </div>
          <div class="grid grid-2">
            <router-link
              v-for="card in recruitCards"
              :key="card.pool"
              :to="`/recruit/${card.pool}`"
              class="recruit-mini"
            >
              <div class="recruit-mini__title">{{ card.title }}</div>
              <p class="recruit-mini__desc">{{ card.desc }}</p>
              <div class="recruit-mini__row">
                <span class="subtle">{{ card.costName }}</span>
                <b :class="itemCount(card.costName) > 0 ? 'gold' : 'subtle'">
                  {{ itemCount(card.costName) }}
                </b>
              </div>
              <span class="recruit-mini__go">前往 →</span>
            </router-link>
          </div>
        </div>

        <div class="panel panel--pad">
          <div class="panel__head">
            <h3>最近战绩</h3>
            <router-link to="/stats" class="home-link">全部 →</router-link>
          </div>

          <div v-if="!records.length" class="empty">还没有开过盒，盒子在角落里看着你。</div>
          <div v-else class="record-list">
            <div
              v-for="r in records"
              :key="r.id"
              class="record-row"
              :class="{ 'record-row--hot': rareRecord(r) }"
            >
              <ItemGlyph :name="r.name" :kind="r.kind" :rarity="r.rarity" :size="24" />
              <span class="record-row__name">{{ r.name }}</span>
              <span class="record-row__qty">×{{ r.qty }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ============================================================
   粗犷战场水墨：低饱和土黄的纸，浓墨压四边，中间留白给交互
   全页只用 黑 / 灰墨 / 一点暗红（印章、高亮）
   ============================================================ */
.home {
  /* 页面内的「纸」比站点默认的深墨亮，局部把文字色反转为墨色 */
  --paper: #1b1611;
  --paper-2: #2a231b;
  --paper-dim: #3d362c;
  --paper-mute: #5c5346;
  --gold: #7d5f26;
  --gold-2: #6f5218;
  --crimson-2: #8b2a2c;
  --azure: #46586a;
  --r-sm: 2px;
  --r-md: 2px;
  --r-lg: 2px;

  position: relative;
  isolation: isolate;
  width: 100%;
  min-height: calc(100vh - 74px);
  padding: 2.3rem 0 3.4rem;
  color: var(--paper-dim);
  background:
    radial-gradient(120% 82% at 14% 0%, rgba(206, 190, 158, 0.75), transparent 62%),
    radial-gradient(90% 70% at 88% 4%, rgba(186, 174, 148, 0.6), transparent 64%),
    radial-gradient(110% 90% at 50% 120%, rgba(152, 139, 116, 0.55), transparent 62%),
    linear-gradient(178deg, #dbd0b9 0%, #d4c8af 40%, #cabc9f 74%, #c0b294 100%);
  /* 四边压暗，让战场元素自然沉进纸里 */
  box-shadow: inset 0 0 150px -30px rgba(26, 21, 16, 0.6);
  overflow: hidden;
}

.home__defs { position: absolute; width: 0; height: 0; overflow: hidden; }

/* ------------------------------ 屏风层 ------------------------------ */
.home__scene {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

.home__art {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.deco {
  position: absolute;
  mix-blend-mode: multiply;
}
/* 靠页面外侧浓、往内淡出：保证绝不压住中间的文字与按钮 */
.deco--banner {
  top: -8px;
  right: -6px;
  left: auto;
  width: min(23vw, 240px);
  transform: scaleX(-1);
  -webkit-mask-image: linear-gradient(102deg, #000 0 44%, rgba(0, 0, 0, 0.45) 66%, transparent 88%);
  mask-image: linear-gradient(102deg, #000 0 44%, rgba(0, 0, 0, 0.45) 66%, transparent 88%);
}
.deco--halberd {
  bottom: 0;
  left: 0;
  width: min(32vw, 360px);
  -webkit-mask-image: linear-gradient(78deg, #000 0 48%, rgba(0, 0, 0, 0.42) 70%, transparent 92%);
  mask-image: linear-gradient(78deg, #000 0 48%, rgba(0, 0, 0, 0.42) 70%, transparent 92%);
}
.deco--grass {
  bottom: 0;
  right: 0;
  width: min(25vw, 300px);
  -webkit-mask-image: linear-gradient(282deg, #000 0 46%, rgba(0, 0, 0, 0.4) 70%, transparent 92%);
  mask-image: linear-gradient(282deg, #000 0 46%, rgba(0, 0, 0, 0.4) 70%, transparent 92%);
}

/* 浮尘：极淡的墨点缓慢上浮 */
.home__dust { position: absolute; inset: 0; }
.home__ground {
  position: absolute;
  inset: auto 0 0;
  height: 24vh;
  background: linear-gradient(180deg, transparent, rgba(44, 36, 28, 0.13) 62%, rgba(38, 31, 24, 0.2));
  -webkit-mask-image: linear-gradient(180deg, transparent, #000 46%);
  mask-image: linear-gradient(180deg, transparent, #000 46%);
}
.dust {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(30, 25, 19, 0.95), rgba(30, 25, 19, 0) 72%);
  opacity: 0;
  animation: dustFloat var(--drift) linear var(--delay) infinite;
  will-change: transform, opacity;
}
@keyframes dustFloat {
  0% { opacity: 0; transform: translate3d(0, 0, 0) scale(0.7); }
  16% { opacity: var(--peak); }
  58% { opacity: calc(var(--peak) * 0.75); }
  100% { opacity: 0; transform: translate3d(var(--dx), var(--dy), 0) scale(1.2); }
}

/* 纸纹与顶部压暗（模拟顶栏投下的影） */
.home__grain {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  opacity: 0.05;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='170' height='170'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='170' height='170' filter='url(%23n)'/%3E%3C/svg%3E");
}
.home__veil {
  position: absolute;
  inset: 0 0 auto;
  height: 74px;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(12, 10, 8, 0.34), rgba(12, 10, 8, 0.08) 52%, transparent);
}
/* 顶栏下方那道撕纸般的墨边 */
.home__edge {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 34px;
  z-index: 2;
  display: block;
  pointer-events: none;
  filter: drop-shadow(0 2px 3px rgba(20, 16, 12, 0.28));
}

.home__inner { position: relative; z-index: 2; }

/* ------------------------------ 标题区 ------------------------------ */
.home-head { margin-bottom: 2.1rem; }

.home-head__eyebrow {
  margin: 0 0 0.9rem;
  font-size: 0.66rem;
  letter-spacing: 0.44em;
  color: var(--paper-mute);
  opacity: 0.85;
}

.home-title-row {
  display: flex;
  align-items: flex-end;
  gap: 0.85rem;
  flex-wrap: wrap;
}

/* 粗犷毛笔书法：字面用墨纹噪声做飞白枯笔 */
.home-title {
  margin: 0;
  font-family: var(--font-serif);
  font-weight: 900;
  font-size: clamp(2.05rem, 5.4vw, 3.5rem);
  line-height: 1.08;
  letter-spacing: 0.06em;
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='b'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.55' numOctaves='4' seed='9'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23b)' opacity='0.5'/%3E%3C/svg%3E"),
    repeating-linear-gradient(112deg, transparent 0 9px, rgba(246, 239, 224, 0.22) 9px 10px, transparent 10px 13px),
    linear-gradient(96deg, #221b14 0%, #0e0b08 34%, #2c241b 58%, #12100c 78%, #1e1811 100%);
  background-size: 160px 160px, 100% 100%, 100% 100%;
  background-blend-mode: soft-light, screen, normal;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 1px 0 rgba(255, 252, 244, 0.45));
}

/* 暗红篆刻印章 */
.home-seal {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2px;
  padding: 7px 6px;
  margin-bottom: 0.55rem;
  flex: none;
  background: rgba(128, 30, 29, 0.82);
  color: #f0e3c9;
  font-family: var(--font-serif);
  font-size: 0.84rem;
  font-weight: 700;
  line-height: 1.05;
  text-align: center;
  letter-spacing: 0;
  transform: rotate(-4deg);
  opacity: 0.66;
  mix-blend-mode: multiply;
  filter: url(#sealEdge);
}

.home-head__greet {
  margin: 1rem 0 0;
  font-family: var(--font-serif);
  font-size: clamp(1rem, 1.9vw, 1.2rem);
  letter-spacing: 0.14em;
  color: var(--paper-dim);
}
.home-head__meta {
  margin: 0.5rem 0 0;
  font-size: 0.84rem;
  line-height: 1.85;
  color: var(--paper-mute);
  max-width: 46rem;
}
.home-head__meta b { color: var(--gold-2); font-variant-numeric: tabular-nums; }

/* ------------------------------ 三个入口 ------------------------------ */
.entries { margin-bottom: 1.2rem; }
.entries__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.9rem;
}
.entries__head h2 {
  font-family: var(--font-serif);
  font-size: 1.12rem;
  letter-spacing: 0.2em;
  color: var(--paper);
  display: flex;
  align-items: center;
  gap: 0.55rem;
}
.entries__head h2::after {
  content: '';
  width: 46px;
  height: 2px;
  background: linear-gradient(90deg, rgba(27, 22, 17, 0.75), transparent);
}
.entries__note { font-size: 0.74rem; letter-spacing: 0.14em; color: var(--paper-mute); }

.entries__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.15rem;
}

/* 毛笔笔触外框：不规则、带墨渍毛边，绝不规整圆角 */
.entry {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 200px;
  padding: 1.3rem 1.25rem 1.05rem;
  border-radius: 0;
  overflow: visible;
  color: var(--paper-dim);
  background:
    linear-gradient(101deg, rgba(56, 50, 41, 0.16), rgba(56, 50, 41, 0.07) 58%, rgba(56, 50, 41, 0.15)),
    radial-gradient(120% 90% at 8% 0%, rgba(255, 250, 240, 0.35), transparent 62%);
  transition: background 0.3s ease, transform 0.24s cubic-bezier(0.2, 0.8, 0.3, 1);
}
/* 毛笔笔触外框：四边粗细不一 + 四角起收笔的墨点，再用位移滤镜抖出墨渍毛边 */
.entry__frame {
  --fr: rgba(24, 19, 14, 0.82);
  position: absolute;
  inset: -5px -4px -6px -5px;
  pointer-events: none;
  background:
    linear-gradient(var(--fr), var(--fr)) left top / 100% 5px no-repeat,
    linear-gradient(var(--fr), var(--fr)) left bottom / 100% 3.5px no-repeat,
    linear-gradient(var(--fr), var(--fr)) left top / 5px 100% no-repeat,
    linear-gradient(var(--fr), var(--fr)) right top / 3.5px 100% no-repeat,
    radial-gradient(circle at 0% 0%, var(--fr) 0 4.5px, transparent 5.1px),
    radial-gradient(circle at 100% 0%, var(--fr) 0 3px, transparent 3.6px),
    radial-gradient(circle at 0% 100%, var(--fr) 0 4px, transparent 4.6px),
    radial-gradient(circle at 100% 100%, var(--fr) 0 4.5px, transparent 5.1px);
  filter: url(#inkEdge);
  transition: opacity 0.3s ease;
}
/* 一笔泼墨：hover / 按下时从角落洇开 */
.entry::after {
  content: '';
  position: absolute;
  left: -6%;
  bottom: -12%;
  width: 72%;
  height: 78%;
  border-radius: 48% 52% 44% 56% / 58% 42% 58% 42%;
  background: radial-gradient(circle at 40% 60%, rgba(28, 23, 17, 0.5), rgba(28, 23, 17, 0) 70%);
  transform: scale(0.2);
  opacity: 0;
  pointer-events: none;
  mix-blend-mode: multiply;
  transition: transform 0.5s cubic-bezier(0.16, 0.9, 0.3, 1), opacity 0.34s ease;
}
.entry:hover {
  transform: translateY(-3px);
  background:
    linear-gradient(101deg, rgba(38, 32, 25, 0.28), rgba(38, 32, 25, 0.16) 58%, rgba(38, 32, 25, 0.26)),
    radial-gradient(120% 90% at 8% 0%, rgba(255, 250, 240, 0.22), transparent 62%);
}
/* hover 只加深墨色，暗红留给箭头/印章这类小面积高亮 */
.entry:hover .entry__frame { --fr: rgba(10, 8, 6, 0.95); }
.entry:hover::after { transform: scale(1); opacity: 0.55; }
.entry:active { transform: translateY(1px); }
.entry:focus-visible { outline: 2px dashed rgba(110, 30, 30, 0.7); outline-offset: 5px; }

.entry__glyph {
  position: absolute;
  right: 0.1rem;
  bottom: -2.6rem;
  font-family: var(--font-serif);
  font-size: 7.6rem;
  line-height: 1;
  font-weight: 900;
  color: rgba(28, 23, 17, 0.07);
  pointer-events: none;
  user-select: none;
  transition: color 0.35s ease, transform 0.45s ease;
  z-index: 0;
}
.entry:hover .entry__glyph { color: rgba(28, 23, 17, 0.11); transform: translateY(-4px); }

.entry__top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.entry__top h3 {
  font-family: var(--font-serif);
  font-size: 1.2rem;
  font-weight: 900;
  letter-spacing: 0.18em;
  color: #17130e;
}

.entry__en {
  position: relative;
  z-index: 1;
  margin: 0.5rem 0 0;
  font-size: 0.57rem;
  letter-spacing: 0.28em;
  color: var(--paper-mute);
  opacity: 0.9;
}
.entry__desc {
  position: relative;
  z-index: 1;
  margin: 0.62rem 0 0;
  font-size: 0.79rem;
  line-height: 1.85;
  color: #4a4237;
  flex: 1;
}
.entry__go {
  position: relative;
  z-index: 1;
  margin-top: 0.95rem;
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 0.86rem;
  letter-spacing: 0.16em;
  color: #17130e;
}
.entry__arrow { transition: transform 0.28s ease; }
.entry:hover .entry__go { color: #8b2a2c; }
.entry:hover .entry__arrow { transform: translateX(4px); }
.entry--locked { opacity: 0.85; }
.entry--locked .entry__go { color: var(--paper-mute); }

/* 主入口（奇珍异宝 / 开始抽取）略重一点墨 */
.entry--primary .entry__frame { --fr: rgba(20, 15, 11, 0.92); }
.entry--primary .entry__go {
  position: relative;
  isolation: isolate;
  padding: 0.4rem 1rem 0.44rem;
  color: #17130e;
}
.entry--primary .entry__go::before {
  content: '';
  position: absolute;
  inset: 0;
  border: 2.5px solid rgba(28, 23, 17, 0.6);
  background: rgba(28, 23, 17, 0.09);
  filter: url(#inkEdge);
}
.entry--primary:hover .entry__go { color: #7c2224; }
.entry--primary:hover .entry__go::before {
  border-color: rgba(14, 11, 8, 0.85);
  background: rgba(14, 11, 8, 0.14);
}

/* ------------------------------ 下半区 ------------------------------ */
.home-lower {
  display: grid;
  grid-template-columns: 1.12fr 0.88fr;
  align-items: start;
  gap: 1.1rem;
  margin-top: 1.35rem;
}

.home .panel {
  background:
    linear-gradient(168deg, rgba(255, 252, 245, 0.62), rgba(232, 222, 202, 0.42));
  border: 1px solid rgba(28, 23, 17, 0.24);
  border-radius: 0;
  box-shadow: none;
  backdrop-filter: blur(1.5px);
}
.home .panel__head h3 { color: #17130e; letter-spacing: 0.14em; }
.home .panel__head h3::before {
  background: linear-gradient(180deg, #6d1f21, rgba(28, 23, 17, 0.85));
  border-radius: 0;
}

.recruit-block { display: flex; flex-direction: column; }
.recruit-block .grid { flex: 1; }

.recruit-mini {
  display: flex;
  flex-direction: column;
  padding: 1rem 1.05rem;
  border-radius: 0;
  border: 1px solid rgba(28, 23, 17, 0.24);
  background: rgba(255, 252, 245, 0.22);
  transition: 0.24s ease;
}
.recruit-mini:hover {
  border-color: rgba(110, 30, 30, 0.55);
  background: rgba(28, 23, 17, 0.08);
}
.recruit-mini__title {
  font-family: var(--font-serif);
  font-weight: 900;
  font-size: 1.02rem;
  letter-spacing: 0.1em;
  color: #17130e;
}
.recruit-mini__desc { font-size: 0.78rem; color: #4a4237; line-height: 1.7; margin: 0.45rem 0 0.7rem; }
.recruit-mini__row { display: flex; justify-content: space-between; font-size: 0.82rem; }
.recruit-mini__go {
  margin-top: auto;
  padding-top: 0.5rem;
  align-self: flex-start;
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  color: #5c5346;
}
.recruit-mini:hover .recruit-mini__go { color: #8b2a2c; }

.home-link {
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  color: #5c5346;
  border-bottom: 1px solid rgba(28, 23, 17, 0.28);
}
.home-link:hover { color: #8b2a2c; border-color: rgba(139, 42, 44, 0.6); }

.record-list { display: grid; gap: 0.12rem; }
.record-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 0.3rem;
  border-bottom: 1px dashed rgba(28, 23, 17, 0.16);
}
.record-row:last-child { border-bottom: 0; }
.record-row--hot { background: linear-gradient(90deg, rgba(139, 42, 44, 0.1), transparent); }
.record-row__name {
  flex: 1;
  font-size: 0.83rem;
  color: #2a241c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.record-row__qty { font-size: 0.76rem; color: #5c5346; font-variant-numeric: tabular-nums; }

.home .empty { color: #5c5346; }

/* 纸面上的稀有度配色统一压深一档，保证可读 */
.home .r-legendary { --rc: #8a6512; --rc-soft: rgba(138, 101, 18, 0.14); }
.home .r-epic { --rc: #66398f; --rc-soft: rgba(102, 57, 143, 0.12); }
.home .r-rare { --rc: #2f5b88; --rc-soft: rgba(47, 91, 136, 0.1); }
.home .r-fine { --rc: #2c6742; --rc-soft: rgba(44, 103, 66, 0.1); }
.home .r-good { --rc: #29657c; --rc-soft: rgba(41, 101, 124, 0.1); }
.home .r-common { --rc: #4b463c; --rc-soft: rgba(75, 70, 60, 0.1); }
.home :deep(.item-card__icon--img) { background: rgba(28, 23, 17, 0.28); }

.home .subtle { color: #5c5346; }
.home .gold { color: var(--gold-2); }

/* ------------------------------ 自适应 ------------------------------ */
@media (max-width: 1080px) {
  .entries__grid { grid-template-columns: 1fr 1fr; }
  .entries__grid > :nth-child(3) { grid-column: 1 / -1; }
  .entry { min-height: 0; }
}
@media (max-width: 980px) {
  .home-lower { grid-template-columns: 1fr; }
}
@media (max-width: 820px) {
  /* 窄屏装饰退场，绝不压住按钮文字 */
  .deco--banner, .deco--grass { display: none; }
  .deco--halberd { width: 210px; opacity: 0.8; }
}
@media (max-width: 620px) {
  .home { padding-top: 1.5rem; }
  .entries__grid { grid-template-columns: 1fr; }
  .entries__head { flex-direction: column; align-items: flex-start; gap: 0.2rem; }
  .home-seal { font-size: 0.6rem; padding: 4px 3px; }
}

@media (prefers-reduced-motion: reduce) {
  .dust { animation: none; opacity: 0.06; }
  .entry, .entry::after, .entry__glyph, .entry__arrow { transition: none; }
}
</style>
