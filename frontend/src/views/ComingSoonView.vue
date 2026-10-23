<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const title = computed(() => route.meta.title || '未命名玩法')
const en = computed(() => route.meta.en || '')
const glyph = computed(() => route.meta.glyph || '阁')
const tone = computed(() => route.meta.tone || 'gold')
const desc = computed(() => route.meta.desc || '')
const plans = computed(() => route.meta.plans || [])
</script>

<template>
  <div class="shell soon">
    <div class="crumbs">
      <router-link to="/" class="crumb">大厅</router-link>
      <span class="crumb-sep">/</span>
      <span class="crumb crumb--current">{{ title }}</span>
    </div>

    <section class="soon-panel panel" :class="`tone--${tone}`">
      <span class="soon-panel__glyph" aria-hidden="true">{{ glyph }}</span>

      <p class="soon-panel__eyebrow">{{ en }}</p>
      <h1 class="page-title soon-panel__title">{{ title }}</h1>
      <span class="soon-panel__badge">建设中 · 暂未开放</span>

      <p class="soon-panel__desc">{{ desc }}</p>

      <ul v-if="plans.length" class="soon-panel__plans">
        <li v-for="p in plans" :key="p">{{ p }}</li>
      </ul>

      <div class="soon-panel__actions">
        <router-link to="/treasure" class="btn btn-primary">去奇珍异宝开盒</router-link>
        <router-link to="/" class="btn btn-ghost">返回大厅</router-link>
      </div>
    </section>
  </div>
</template>

<style scoped>
.soon { padding-top: 1.8rem; }

.crumbs { display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; margin-bottom: 1.3rem; }
.crumb { color: var(--paper-mute); }
.crumb:hover { color: var(--gold); }
.crumb--current { color: var(--paper-dim); }
.crumb-sep { color: #4d453a; }

.soon-panel {
  --tone: var(--gold);
  position: relative;
  overflow: hidden;
  padding: 3.2rem 2rem 2.6rem;
  text-align: center;
  display: grid;
  justify-items: center;
  min-height: 460px;
  align-content: center;
  background:
    radial-gradient(70% 55% at 50% 0%, color-mix(in srgb, var(--tone) 16%, transparent), transparent 70%),
    linear-gradient(170deg, rgba(38, 33, 29, 0.94), rgba(16, 14, 13, 0.96));
  border-color: color-mix(in srgb, var(--tone) 26%, transparent);
}
.tone--violet { --tone: var(--violet); }
.tone--azure { --tone: var(--azure); }

.soon-panel__glyph {
  position: absolute;
  right: -2rem;
  bottom: -5rem;
  font-family: var(--font-serif);
  font-size: 22rem;
  line-height: 1;
  color: var(--tone);
  opacity: 0.055;
  pointer-events: none;
  user-select: none;
}

.soon-panel__eyebrow {
  margin: 0;
  font-size: 0.68rem;
  letter-spacing: 0.44em;
  color: var(--paper-mute);
}
.soon-panel__title {
  margin: 0.7rem 0 0;
  font-size: clamp(1.9rem, 4.4vw, 2.7rem);
  letter-spacing: 0.22em;
  color: var(--paper);
  text-shadow: 0 0 34px color-mix(in srgb, var(--tone) 32%, transparent);
}
.soon-panel__badge {
  margin-top: 1.05rem;
  padding: 0.28rem 0.9rem;
  border-radius: 999px;
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  color: var(--tone);
  border: 1px solid color-mix(in srgb, var(--tone) 42%, transparent);
  background: color-mix(in srgb, var(--tone) 10%, transparent);
}
.soon-panel__desc {
  margin: 1.35rem 0 0;
  max-width: 44ch;
  font-size: 0.88rem;
  line-height: 1.9;
  color: var(--paper-mute);
}

.soon-panel__plans {
  margin: 1.5rem 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
  font-size: 0.82rem;
  color: var(--paper-dim);
}
.soon-panel__plans li::before {
  content: '◦';
  color: var(--tone);
  margin-right: 0.5rem;
  opacity: 0.8;
}

.soon-panel__actions {
  margin-top: 2rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
}

@media (max-width: 560px) {
  .soon-panel { padding: 2.4rem 1.15rem 2rem; min-height: 400px; }
  .soon-panel__glyph { font-size: 14rem; right: -1.5rem; bottom: -3.5rem; }
}
</style>
