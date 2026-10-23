<script setup>
import ItemGlyph from './ItemGlyph.vue'

defineProps({
  entries: { type: Array, default: () => [] },
  limit: { type: Number, default: 12 },
  showBar: { type: Boolean, default: true },
})

const RARITY_NAME = {
  legendary: '传说', epic: '史诗', rare: '稀有',
  fine: '精良', good: '精品', common: '普通',
}
</script>

<template>
  <div>
    <div v-for="e in entries.slice(0, limit)" :key="e.key + e.name" class="prob-row" :class="`r-${e.rarity}`">
      <div class="prob-row__main">
        <ItemGlyph :name="e.name" :kind="e.kind" :rarity="e.rarity" :size="22" />
        <span class="prob-row__name">
          {{ e.name }}<span v-if="e.qty > 1" class="subtle"> ×{{ e.qty }}</span>
        </span>
        <span class="rarity-tag" :class="`r-${e.rarity}`">{{ RARITY_NAME[e.rarity] }}</span>
      </div>
      <span class="prob-row__value">{{ e.probability.toFixed(e.probability < 0.1 ? 3 : 2) }}%</span>
      <div v-if="showBar" class="prob-track">
        <div class="prob-fill" :style="{ width: `${Math.max(1.2, Math.min(100, e.probability))}%` }" />
      </div>
    </div>
  </div>
</template>
