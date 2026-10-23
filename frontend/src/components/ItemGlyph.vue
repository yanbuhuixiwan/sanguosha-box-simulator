<script setup>
import { computed, ref, watch } from 'vue'
import { mediaUrl, focusPosition } from '../assets/media.js'

const props = defineProps({
  name: { type: String, required: true },
  kind: { type: String, default: 'item' },
  rarity: { type: String, default: 'common' },
  size: { type: Number, default: 46 },
  // 结算图里武将/皮肤用名字首字，避免整屏都是「将」
  nameGlyph: { type: Boolean, default: false },
})

const GLYPHS = [
  // 「雁翎甲」必须排在「雁翎」前面，否则「雁翎甲」会被先匹配成「翎」
  ['招募令', '令'], ['雁翎甲', '甲'], ['雁翎', '翎'], ['换将卡', '换'], ['手气卡', '运'],
  ['点将卡', '将'], ['进阶丹', '丹'], ['菜篮子', '篮'], ['欢乐豆', '豆'],
  ['双倍经验卡', '倍'], ['经验卡', '倍'], ['银币', '币'],
  ['宝珠碎片', '碎'], ['碎片', '碎'], ['皮肤包', '肤'], ['宝珠', '珠'], ['将魂', '魂'], ['体验卡', '验'],
  ['天工石', '石'], ['迷迭珠', '珠'],
]

// 有素材图就用图，没有对应图时退回原来的字形
const src = computed(() => mediaUrl(props.name, props.kind))
const failed = ref(false)
watch(src, () => { failed.value = false })
const showImg = computed(() => !!src.value && !failed.value)

const glyph = computed(() => {
  if (props.nameGlyph && (props.kind === 'hero' || props.kind === 'skin')) {
    const clean = props.name.replace(/[*·\s]/g, '')
    // 「SP赵云」这类前缀取首个汉字，别显示成字母 S
    const han = clean.match(/[\u4e00-\u9fa5]/)
    if (han) return han[0]
    if (clean) return clean[0]
  }
  if (props.kind === 'hero') return '将'
  if (props.kind === 'skin') return '皮'
  for (const [key, ch] of GLYPHS) {
    if (props.name.includes(key)) return ch
  }
  return '物'
})
</script>

<template>
  <span
    class="item-card__icon"
    :class="[`r-${rarity}`, { 'item-card__icon--img': showImg }]"
    :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${size * 0.42}px` }"
  >
    <img
      v-if="showImg"
      :src="src"
      :alt="name"
      loading="lazy"
      decoding="async"
      :style="{ objectPosition: focusPosition(kind) }"
      @error="failed = true"
    />
    <template v-else>{{ glyph }}</template>
  </span>
</template>
