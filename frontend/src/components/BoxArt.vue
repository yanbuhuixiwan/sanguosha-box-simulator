<script setup>
import { computed } from 'vue'

const props = defineProps({
  theme: { type: String, default: 'crimson' },
  size: { type: Number, default: 220 },
})

/**
 * 乌木宝匣（方案 A）
 * ---------------------------------------------------------------
 * 不做生日礼盒：没有蝴蝶结、没有塑料高光、没有玻璃反光。
 * 只有：乌木匣体 + 木纹 + 米白暗纹帛带 + 朱砂「礼」封印 + 铜包角。
 * 六个主题只在「乌木偏暖 / 偏青」与帛带米白深浅上做极小偏移，
 * 全部落在焦墨—赭褐—朱砂—米白四色区间内，不新增色相。
 *
 * 明度关系（关键）：匣子要站在「案面聚光」里，不能比背景还暗，
 * 否则会变成一块黑洞。顶面 > 盖前 > 匣体 > 底面。
 */
const woods = {
  // 绛红战旗匣
  crimson: { hi: '#8d6543', mid: '#63452c', lo: '#3f2d20', ribbon: '#e6d9bc', ribbonLo: '#9c8a67' },
  // 秋收金匣
  gold: { hi: '#916e48', mid: '#684c2c', lo: '#412f1e', ribbon: '#e3d7ba', ribbonLo: '#998763' },
  // 暑期青檀匣（偏冷，但仍压在墨褐里）
  azure: { hi: '#8a7f6c', mid: '#665c4c', lo: '#423a31', ribbon: '#dcd2b6', ribbonLo: '#968d75' },
  // 琥珀匣
  amber: { hi: '#976845', mid: '#6a472a', lo: '#432b1a', ribbon: '#e9dbb8', ribbonLo: '#a48f6a' },
  // 紫檀匣
  plum: { hi: '#7d5445', mid: '#543729', lo: '#37251b', ribbon: '#e0d4be', ribbonLo: '#9f8d76' },
}

const p = computed(() => woods[props.theme] || woods.crimson)
const uid = computed(() => `box-${props.theme}`)
</script>

<template>
  <svg
    :width="size"
    :height="size * 1.12"
    viewBox="0 0 200 224"
    fill="none"
    class="box-art"
    role="img"
    aria-label="乌木宝匣"
  >
    <defs>
      <!-- 匣体：上暖下沉，靠明度差出体积，不靠高光 -->
      <linearGradient :id="`${uid}-wood`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="p.mid" />
        <stop offset="38%" :stop-color="p.mid" />
        <stop offset="100%" :stop-color="p.lo" />
      </linearGradient>
      <linearGradient :id="`${uid}-lid-top`" x1="0" y1="0" x2="0.15" y2="1">
        <stop offset="0%" :stop-color="p.hi" />
        <stop offset="100%" :stop-color="p.mid" />
      </linearGradient>
      <linearGradient :id="`${uid}-lid-front`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="p.mid" />
        <stop offset="72%" :stop-color="p.lo" />
      </linearGradient>
      <!-- 帛带：横向明暗，像一条绕上去的织物 -->
      <linearGradient :id="`${uid}-ribbon`" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" :stop-color="p.ribbonLo" />
        <stop offset="24%" :stop-color="p.ribbon" />
        <stop offset="64%" :stop-color="p.ribbon" />
        <stop offset="100%" :stop-color="p.ribbonLo" />
      </linearGradient>
      <!-- 落地影 -->
      <radialGradient :id="`${uid}-shadow`" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#000000" stop-opacity="0.66" />
        <stop offset="60%" stop-color="#000000" stop-opacity="0.3" />
        <stop offset="100%" stop-color="#000000" stop-opacity="0" />
      </radialGradient>
      <!-- 案上一点暖反光（环境漫反射，不是高光） -->
      <radialGradient :id="`${uid}-pool`" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#a67c4e" stop-opacity="0.22" />
        <stop offset="100%" stop-color="#a67c4e" stop-opacity="0" />
      </radialGradient>
      <!-- 体贴的环境光：左上极淡、右下收敛 -->
      <linearGradient :id="`${uid}-ambient`" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#ece2ca" stop-opacity="0.075" />
        <stop offset="44%" stop-color="#ece2ca" stop-opacity="0.015" />
        <stop offset="100%" stop-color="#000000" stop-opacity="0.13" />
      </linearGradient>
      <!-- 左右两侧收暗：让正立面读成一块有厚度的板，而不是一张色卡 -->
      <linearGradient :id="`${uid}-side`" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#000000" stop-opacity="0.26" />
        <stop offset="14%" stop-color="#000000" stop-opacity="0.06" />
        <stop offset="46%" stop-color="#ece2ca" stop-opacity="0.05" />
        <stop offset="78%" stop-color="#000000" stop-opacity="0.05" />
        <stop offset="100%" stop-color="#000000" stop-opacity="0.3" />
      </linearGradient>
      <!-- 帛带暗纹：斜向细织纹 -->
      <pattern
        :id="`${uid}-weave`"
        width="5"
        height="5"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)"
      >
        <path d="M0 0 V5" stroke="#8a7856" stroke-width="0.9" opacity="0.42" />
      </pattern>
      <clipPath :id="`${uid}-body-clip`">
        <rect x="31" y="97" width="138" height="95" />
      </clipPath>
      <clipPath :id="`${uid}-ribbon-clip`">
        <rect x="89" y="58" width="22" height="134" />
      </clipPath>
    </defs>

    <!-- 1) 落影 + 案面暖反光（很轻，只把匣子“放”在案上） -->
    <ellipse cx="100" cy="201" rx="74" ry="12" :fill="`url(#${uid}-shadow)`" />
    <ellipse cx="100" cy="199" rx="54" ry="7.5" :fill="`url(#${uid}-pool)`" opacity="0.55" />

    <!-- 2) 匣体 -->
    <rect x="31" y="97" width="138" height="95" :fill="`url(#${uid}-wood)`" />
    <g :clip-path="`url(#${uid}-body-clip)`">
      <!-- 木纹：竖向细丝，深浅交错 -->
      <g stroke="#0d0a07" fill="none" stroke-linecap="round" opacity="0.3">
        <path d="M44 97 C50 124 43 152 48 192" stroke-width="1.1" />
        <path d="M59 97 C64 122 56 150 62 192" stroke-width="0.9" />
        <path d="M73 97 C77 118 71 146 75 192" stroke-width="1.2" />
        <path d="M121 97 C125 120 119 150 123 192" stroke-width="1" />
        <path d="M137 97 C142 124 134 152 140 192" stroke-width="1.1" />
        <path d="M153 97 C157 122 151 148 156 192" stroke-width="0.9" />
        <path d="M88 97 C91 122 85 150 89 192" stroke-width="0.8" opacity="0.7" />
        <path d="M108 97 C112 124 106 152 110 192" stroke-width="0.8" opacity="0.6" />
      </g>
      <g stroke="#b08a62" fill="none" stroke-linecap="round" opacity="0.12">
        <path d="M51 97 C56 120 49 148 54 192" stroke-width="2.4" />
        <path d="M129 97 C134 118 127 146 132 192" stroke-width="2.2" />
        <path d="M161 97 C165 122 159 150 163 192" stroke-width="1.8" />
      </g>
      <!-- 匣体上下沿的暗压，让木头有厚度 -->
      <rect x="31" y="97" width="138" height="13" fill="#000000" opacity="0.26" />
      <rect x="31" y="97" width="138" height="95" :fill="`url(#${uid}-side)`" />
      <!-- 环境光罩 -->
      <rect x="31" y="97" width="138" height="95" :fill="`url(#${uid}-ambient)`" />
    </g>
    <rect x="31" y="97" width="138" height="95" stroke="#a67c4e" stroke-opacity="0.22" />
    <!-- 匣体贴地的一线暗，把箱子“压”在案上 -->
    <rect x="31" y="188" width="138" height="4" fill="#000000" opacity="0.35" />

    <!-- 3) 铜包角（下两角），边角磨损 -->
    <path d="M31 177 L31 192 L48 192 L48 187 L36 187 L36 177 Z" fill="#a67c4e" opacity="0.36" />
    <path d="M169 177 L169 192 L152 192 L152 187 L164 187 L164 177 Z" fill="#a67c4e" opacity="0.3" />
    <g stroke="#d8c39c" stroke-linecap="round" opacity="0.18">
      <path d="M38 186.6 L45 185" stroke-width="0.9" />
      <path d="M157 186.2 L163 185.2" stroke-width="0.7" />
      <path d="M163 101.6 L167.6 102.6" stroke-width="0.7" opacity="0.7" />
    </g>

    <!-- 4) 匣盖：顶面 + 前面，靠明度分层，无高光条 -->
    <rect x="23" y="58" width="154" height="15" :fill="`url(#${uid}-lid-top)`" />
    <rect x="23" y="73" width="154" height="24" :fill="`url(#${uid}-lid-front)`" />
    <g stroke="#0d0a07" opacity="0.18" fill="none" stroke-linecap="round">
      <path d="M28 63.4 H172" stroke-width="0.9" />
      <path d="M28 67.6 H172" stroke-width="0.7" />
      <path d="M28 78.4 H172" stroke-width="0.8" />
      <path d="M28 85.2 H172" stroke-width="0.6" />
    </g>
    <!-- 盖棱受光：一条极细的赭石金，代替塑料高光 -->
    <path d="M23 58.5 H177" stroke="#c9a46e" stroke-opacity="0.34" />
    <path d="M23 73.2 H177" stroke="#c9a46e" stroke-opacity="0.42" />
    <rect x="23" y="75" width="154" height="1.4" fill="#0b0806" opacity="0.35" />
    <rect x="23" y="95.4" width="154" height="1.6" fill="#0b0806" opacity="0.5" />
    <rect x="23" y="97" width="154" height="5" fill="#000000" opacity="0.24" />
    <rect x="23" y="58" width="154" height="39" :fill="`url(#${uid}-side)`" opacity="0.9" />
    <rect x="23" y="58" width="154" height="39" :fill="`url(#${uid}-ambient)`" opacity="0.8" />

    <!-- 5) 帛带：米白暗纹，绕匣一周 -->
    <rect x="89" y="58" width="22" height="134" :fill="`url(#${uid}-ribbon)`" />
    <g :clip-path="`url(#${uid}-ribbon-clip)`">
      <rect x="89" y="58" width="22" height="134" :fill="`url(#${uid}-weave)`" opacity="0.26" />
      <!-- 绕过盖顶的面：受压更暗 -->
      <rect x="89" y="58" width="22" height="15" fill="#000000" opacity="0.14" />
      <!-- 盖沿投影压在帛带上，帛带才有“绕过去”的转折 -->
      <rect x="89" y="73" width="22" height="7" fill="#000000" opacity="0.2" />
      <rect x="89" y="92" width="22" height="9" fill="#000000" opacity="0.16" />
      <rect x="89" y="58" width="4" height="134" fill="#000000" opacity="0.1" />
      <rect x="107" y="58" width="4" height="134" fill="#000000" opacity="0.14" />
      <!-- 两道折痕 + 落地沉影：免得帛带变成一根白柱子 -->
      <rect x="89" y="117" width="22" height="2.2" fill="#000000" opacity="0.11" />
      <rect x="89" y="119.2" width="22" height="1" fill="#efe6cd" opacity="0.16" />
      <rect x="89" y="159" width="22" height="2.4" fill="#000000" opacity="0.1" />
      <rect x="89" y="161.4" width="22" height="1" fill="#efe6cd" opacity="0.12" />
      <rect x="89" y="174" width="22" height="18" fill="#000000" opacity="0.18" />
    </g>
    <path d="M89 58 V192" stroke="#7a6849" stroke-opacity="0.4" stroke-width="0.8" />
    <path d="M111 58 V192" stroke="#7a6849" stroke-opacity="0.34" stroke-width="0.8" />

    <!-- 6) 朱砂「礼」封印：整个盒子的记忆点 -->
    <g transform="translate(100 148) rotate(-1.6)">
      <rect x="-20" y="-20" width="40" height="40" rx="2" fill="#9e2b25" />
      <rect x="-20" y="-20" width="40" height="40" rx="2" fill="#000000" opacity="0.08" />
      <rect
        x="-16.5" y="-16.5" width="33" height="33"
        fill="none" stroke="#f2e3c6" stroke-opacity="0.46" stroke-width="1.1"
      />
      <text
        x="0" y="8.4"
        text-anchor="middle"
        font-size="22"
        font-family="Songti SC, SimSun, STSong, serif"
        fill="#f6e7cc"
      >礼</text>
      <!-- 印边一点点崩口，避免像贴图 -->
      <rect x="11" y="-20.6" width="5.4" height="2.6" :fill="p.ribbon" opacity="0.5" />
      <rect x="-19.6" y="13" width="2.4" height="4" :fill="p.ribbon" opacity="0.4" />
    </g>
  </svg>
</template>
