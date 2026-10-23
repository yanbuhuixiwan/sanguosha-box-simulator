import map from './media-map.json'

/** 「霜刃绚练·灵雎动态包」-> { hero: '灵雎', skin: '霜刃绚练' }；规则与 tools/build_media_map.py 一致 */
export function parseSkinName(text) {
  const n = String(text || '').replace(/动态包/g, '').trim()
  const m = n.split(/[·*＊]/)
  return m.length > 1 ? { hero: m[1].trim(), skin: m[0].trim() } : { hero: '', skin: n }
}

/**
 * 名称 -> 可访问的素材图地址；查不到返回空串。
 * kind: item / hero / skin
 */
export function mediaUrl(name, kind = 'item') {
  if (!name) return ''
  let rel = ''
  if (kind === 'hero') {
    rel = map.heroes?.[name] || ''
  } else if (kind === 'skin') {
    const { hero, skin } = parseSkinName(name)
    rel = map.skins?.[`${hero}_${skin}`] || ''
  } else {
    rel = map.items?.[name] || ''
  }
  if (!rel) return ''
  // 逐段编码：中文目录名与文件名都要转义
  return '/api/media/' + rel.split('/').map(encodeURIComponent).join('/')
}

/** 武将是 3:4 立绘，裁切时焦点压在上半部（脸）；皮肤是横图取中段 */
export function focusPosition(kind) {
  if (kind === 'hero') return '50% 14%'
  if (kind === 'skin') return '50% 38%'
  return '50% 50%'
}

export const mediaStats = {
  items: Object.keys(map.items || {}).length,
  heroes: Object.keys(map.heroes || {}).length,
  skins: Object.keys(map.skins || {}).length,
}
