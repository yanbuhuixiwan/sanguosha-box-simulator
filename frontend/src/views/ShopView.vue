<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import ItemGlyph from '../components/ItemGlyph.vue'
import { useToast } from '../composables/useToast'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const { success: toastSuccess, error: toastError } = useToast()

const loading = ref(true)
const items = ref([])
const qty = ref(1)
const buying = ref('')

const QTY_OPTIONS = [1, 5, 10, 50]

const yuanbao = computed(() => auth.yuanbao)
const RARITY_NAME = { legendary: '传说', epic: '史诗', rare: '稀有', common: '普通' }

const total = (item) => item.price * qty.value
const affordable = (item) => yuanbao.value >= total(item)

async function load() {
  loading.value = true
  try {
    const res = await api.shop()
    items.value = res.items
    auth.setYuanbao(res.yuanbao)
  } catch (err) {
    toastError(err.message)
  } finally {
    loading.value = false
  }
}

async function buy(item) {
  if (buying.value) return
  buying.value = item.key
  try {
    const res = await api.buyItem(item.key, qty.value)
    auth.setYuanbao(res.yuanbao)
    item.owned = res.owned
    toastSuccess(`购入「${res.name}」× ${res.count}，花费 ${res.spent.toLocaleString('zh-CN')} 元宝`)
  } catch (err) {
    toastError(err.message)
  } finally {
    buying.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="shell shop-page">
    <div class="crumbs">
      <router-link to="/" class="crumb">大厅</router-link>
      <span class="crumb-sep">/</span>
      <span class="crumb crumb--current">补给商店</span>
    </div>

    <section class="panel shop-head">
      <div>
        <h1 class="page-title">补给商店 <span class="seal">明码</span></h1>
        <p class="subtle shop-head__desc">
          元宝换凭证，凭证换武将和皮肤。买来的凭证与礼盒开出的自动合并计数，不区分来源。
        </p>
      </div>
      <div class="shop-wallet">
        <span class="shop-wallet__label">当前元宝</span>
        <span class="shop-wallet__value">{{ yuanbao.toLocaleString('zh-CN') }}</span>
        <router-link to="/" class="shop-wallet__hint">不够就去开盒攒 →</router-link>
      </div>
    </section>

    <div v-if="loading" class="empty">正在整理货架……</div>

    <template v-else>
      <section class="qty-bar">
        <span class="qty-bar__label">购买数量</span>
        <button
          v-for="n in QTY_OPTIONS"
          :key="n"
          class="chip chip--sm"
          :class="{ 'chip--active': qty === n }"
          @click="qty = n"
        >
          {{ n }} 个
        </button>
      </section>

      <div class="shop-grid">
        <article v-for="item in items" :key="item.key" class="panel shop-card" :class="`r-${item.rarity}`">
          <div class="shop-card__top">
            <ItemGlyph :name="item.name" :kind="item.kind" :rarity="item.rarity" :size="54" />
            <div class="shop-card__title">
              <div class="shop-card__name">
                {{ item.name }}
                <span class="rarity-tag" :class="`r-${item.rarity}`">{{ RARITY_NAME[item.rarity] }}</span>
              </div>
              <div class="shop-card__tag">{{ item.tag }}</div>
            </div>
            <div class="shop-card__owned">
              <span class="shop-card__owned-label">已持有</span>
              <span class="shop-card__owned-value">{{ item.owned }}</span>
            </div>
          </div>

          <p class="shop-card__desc">{{ item.desc }}</p>

          <div class="shop-card__foot">
            <div class="price">
              <span class="price__num">{{ item.price.toLocaleString('zh-CN') }}</span>
              <span class="price__unit">元宝 / 个</span>
            </div>
            <button
              class="btn btn-gold shop-card__buy"
              :disabled="!affordable(item) || buying === item.key"
              @click="buy(item)"
            >
              {{ buying === item.key ? '购买中…' : `买 ${qty} 个 · ${total(item).toLocaleString('zh-CN')}` }}
            </button>
          </div>
          <p v-if="!affordable(item)" class="shop-card__warn">
            元宝不足，还差 {{ (total(item) - yuanbao).toLocaleString('zh-CN') }}
          </p>
        </article>
      </div>

      <p class="subtle shop-foot">
        价格写在 <code>backend/app/data/shop.json</code>，改完重启后端即生效。
      </p>
    </template>
  </div>
</template>

<style scoped>
.shop-page { padding-top: 1.8rem; }

.crumbs { display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; margin-bottom: 1.1rem; }
.crumb { color: var(--paper-mute); }
.crumb:hover { color: var(--gold); }
.crumb--current { color: var(--paper-dim); }
.crumb-sep { color: #4d453a; }

.shop-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
  padding: 1.4rem 1.6rem;
  overflow: hidden;
  border-color: rgba(166, 124, 78, 0.22);
  background-color: var(--ink-700);
  background-image: linear-gradient(172deg, rgba(48, 41, 34, 0.94), rgba(28, 24, 21, 0.97));
}
/* 旧宣纸横幅：只在顶边留一丝干笔飞白，不做紫红渐变 */
.shop-head::after {
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
.shop-head__desc { margin: 0.6rem 0 0; font-size: 0.85rem; line-height: 1.8; max-width: 40em; }

/* 元宝：竹简信息块 */
.shop-wallet {
  display: grid;
  gap: 0.15rem;
  padding: 0.62rem 1rem;
  border-radius: 2px;
  border: 1px solid rgba(166, 124, 78, 0.26);
  background:
    repeating-linear-gradient(90deg, rgba(236, 226, 202, 0.028) 0 1px, transparent 1px 9px),
    linear-gradient(180deg, rgba(58, 50, 42, 0.66), rgba(31, 27, 23, 0.86));
  box-shadow: inset 0 0 0 1px rgba(20, 17, 14, 0.5);
  text-align: right;
}
.shop-wallet__label { font-size: 0.68rem; letter-spacing: 0.18em; color: var(--paper-mute); }
.shop-wallet__value {
  font-family: var(--font-num);
  font-weight: 700;
  font-size: 1.5rem;
  color: var(--gold-2);
  font-variant-numeric: tabular-nums;
  line-height: 1.3;
}
.shop-wallet__hint { font-size: 0.72rem; color: var(--paper-mute); }
.shop-wallet__hint:hover { color: var(--gold); }

.qty-bar {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin: 1.2rem 0 0.9rem;
  flex-wrap: wrap;
}
.qty-bar__label {
  font-size: 0.74rem;
  letter-spacing: 0.18em;
  color: var(--paper-mute);
  margin-right: 0.3rem;
}
.chip--sm { flex: none; padding: 0.34rem 0.75rem; font-size: 0.78rem; }

.shop-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
  gap: 1rem;
}

.shop-card {
  padding: 1.3rem 1.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  overflow: hidden;
  border-radius: 2px;
  /* 卡片统一 #2D2720 旧宣纸底，稀有度只用印戳表达，不再铺彩色光晕 */
  border-color: rgba(166, 124, 78, 0.2);
  background-color: var(--ink-700);
  background-image: linear-gradient(170deg, rgba(45, 39, 32, 0.93), rgba(24, 21, 18, 0.96));
}
/* 局部枯笔毛边：左上起笔，到 2/3 处断掉 */
.shop-card::after {
  content: '';
  position: absolute;
  left: 4%;
  right: 34%;
  top: 0;
  height: 2px;
  background-image: var(--tex-drybrush);
  background-repeat: repeat-x;
  background-size: 240px 16px;
  opacity: 0.26;
  pointer-events: none;
}
.shop-card__top { display: flex; align-items: center; gap: 0.85rem; }
.shop-card__title { min-width: 0; flex: 1; }
.shop-card__name {
  font-family: var(--font-serif);
  font-size: 1.12rem;
  color: var(--paper);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.shop-card__tag { font-size: 0.74rem; color: var(--paper-mute); margin-top: 0.25rem; letter-spacing: 0.06em; }
.shop-card__owned { text-align: right; flex: none; }
.shop-card__owned-label { display: block; font-size: 0.66rem; letter-spacing: 0.14em; color: var(--paper-mute); }
.shop-card__owned-value {
  font-family: var(--font-serif);
  font-size: 1.2rem;
  color: var(--rc);
  font-variant-numeric: tabular-nums;
}

.shop-card__desc { margin: 0; font-size: 0.82rem; line-height: 1.75; color: var(--paper-mute); }

.shop-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: auto;
  padding-top: 0.9rem;
  border-top: 1px solid rgba(236, 226, 202, 0.1);
}
.price { display: flex; align-items: baseline; gap: 0.3rem; }
.price__num {
  font-family: var(--font-num);
  font-weight: 700;
  font-size: 1.5rem;
  color: var(--gold-2);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.price__unit { font-size: 0.72rem; color: var(--paper-mute); }
.shop-card__buy { flex: none; min-width: 9.5em; }

.shop-card__warn { margin: 0; font-size: 0.74rem; color: var(--crimson-2); }

.shop-foot { margin-top: 1.4rem; font-size: 0.76rem; color: #7a7060; }
.shop-foot code {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 0.72rem;
  color: var(--paper-dim);
  background: rgba(236, 226, 202, 0.06);
  padding: 1px 5px;
  border-radius: 2px;
}

@media (max-width: 620px) {
  .shop-head { flex-direction: column; align-items: flex-start; }
  .shop-wallet { width: 100%; text-align: left; }
  .shop-grid { grid-template-columns: 1fr; }
  .shop-card__foot { flex-wrap: wrap; }
  .shop-card__buy { width: 100%; }
}
</style>
