const BASE = import.meta.env.VITE_API_BASE || '/api'
const TOKEN_KEY = 'sgs_token'

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY) || '',
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = tokenStore.get()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (err) {
    throw new Error('连不上服务器，后端大概在摸鱼')
  }

  if (res.status === 204) return null

  let payload = null
  const text = await res.text()
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!res.ok) {
    const detail = payload?.detail
    const msg =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join('；')
          : `请求失败（${res.status}）`
    if (res.status === 401 && auth) {
      tokenStore.clear()
      // 通知上层把 store 里的 token 也清掉（api 模块不该直接依赖 pinia store）
      window.dispatchEvent(new Event('sgs:unauthorized'))
    }
    throw new Error(msg)
  }
  return payload
}

export const api = {
  register: (username, password, nickname) =>
    request('/auth/register', { method: 'POST', auth: false, body: { username, password, nickname } }),
  login: (username, password) =>
    request('/auth/login', { method: 'POST', auth: false, body: { username, password } }),
  me: () => request('/me'),
  recharge: (amount) => request('/me/recharge', { method: 'POST', body: { amount } }),
  boxes: () => request('/boxes'),
  openBox: (boxId, count) => request(`/boxes/${boxId}/open`, { method: 'POST', body: { count } }),
  pool: (poolId) => request(`/recruit/${poolId}`),
  pull: (poolId, count) => request(`/recruit/${poolId}/pull`, { method: 'POST', body: { count } }),
  inventory: () => request('/inventory'),
  decompose: (key, count = 1) =>
    request('/inventory/decompose', { method: 'POST', body: { key, count } }),
  openItem: (key, count = 1) =>
    request('/inventory/open', { method: 'POST', body: { key, count } }),
  palace: (period = '') => request(`/palace${period ? `?period=${encodeURIComponent(period)}` : ''}`),
  palacePull: (count, period = '') => request('/palace/pull', { method: 'POST', body: { count, period } }),
  corridor: (period = '') => request(`/corridor${period ? `?period=${encodeURIComponent(period)}` : ''}`),
  corridorRecall: (count, period = '') => request('/corridor/recall', { method: 'POST', body: { count, period } }),
  shop: () => request('/shop'),
  buyItem: (item_key, count) => request('/shop/buy', { method: 'POST', body: { item_key, count } }),
  records: (limit = 30, { source = '', boxId = '' } = {}) => {
    const q = new URLSearchParams({ limit: String(limit) })
    if (source) q.set('source', source)
    if (boxId) q.set('box_id', boxId)
    return request(`/records?${q.toString()}`)
  },
  stats: () => request('/stats'),
  meta: () => request('/meta', { auth: false }),
  odds: () => request('/odds', { auth: false }),
}
