// 布局探针：打开页面，找出所有超出视口宽度的元素，以及页面整体滚动宽度。
// 用法：MOBILE=1 node tools/probe.mjs "<登录token或 login:用户:密码>" "/corridor"
import { spawn } from 'node:child_process'
import path from 'node:path'

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = 9337
const BASE = 'http://127.0.0.1:8080'
const token = process.argv[2]
const page = process.argv[3] || '/'
const extra = process.argv[4] || ''
const loginUser = process.env.QA_USER || 'corrtest1'
const loginPass = process.env.QA_PASS || 'test1234'
const profile = path.join(process.env.TEMP || '.', `sgs-probe-${Date.now()}`)

const chrome = spawn(CHROME, [
  '--headless=new',
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`,
  '--window-size=1440,1000',
  '--hide-scrollbars',
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-gpu',
  'about:blank',
], { stdio: 'ignore' })

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function targetWs() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
      const p = list.find((t) => t.type === 'page')
      if (p) return p.webSocketDebuggerUrl
    } catch { /* waiting */ }
    await sleep(250)
  }
  throw new Error('chrome 启动超时')
}

const ws = new WebSocket(await targetWs())
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
let seq = 0
const pending = new Map()
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) {
    const { resolve, reject } = pending.get(m.id)
    pending.delete(m.id)
    m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result)
  }
}
const send = (method, params = {}) => {
  const id = ++seq
  ws.send(JSON.stringify({ id, method, params }))
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
}

await send('Page.enable')
await send('Runtime.enable')
if (process.env.MOBILE === '1') {
  await send('Emulation.setDeviceMetricsOverride', {
    width: 390, height: 844, deviceScaleFactor: 2, mobile: true,
  })
}

await send('Page.navigate', { url: `${BASE}/login` })
await sleep(1500)
const auth = await send('Runtime.evaluate', {
  expression: `fetch('${BASE}/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:${JSON.stringify(loginUser)},password:${JSON.stringify(loginPass)}})})
    .then(r=>r.json()).then(d=>{localStorage.setItem('sgs_token',d.token);return 'ok'}).catch(e=>'fail:'+e.message)`,
  returnByValue: true, awaitPromise: true,
})
if (auth.result.value !== 'ok') { console.log('登录失败', auth.result.value); process.exit(1) }

await send('Page.navigate', { url: `${BASE}${page}${page.includes('?') ? '&' : '?'}t=${Date.now()}` })
await sleep(2800)

const probe = await send('Runtime.evaluate', {
  expression: `(() => {
    const vw = document.documentElement.clientWidth;
    const out = [];
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      const right = r.left + r.width;
      if (right > vw + 1 || r.left < -1) {
        const cs = getComputedStyle(el);
        out.push({
          tag: el.tagName.toLowerCase(),
          cls: (el.className && String(el.className).slice(0, 60)) || '',
          left: Math.round(r.left), right: Math.round(right), w: Math.round(r.width),
          overflowX: cs.overflowX, pos: cs.position,
          parent: el.parentElement ? el.parentElement.className && String(el.parentElement.className).slice(0, 40) : '',
        });
      }
    }
    out.sort((a, b) => b.right - a.right);
    return JSON.stringify({
      vw,
      docScroll: document.documentElement.scrollWidth,
      bodyScroll: document.body.scrollWidth,
      count: out.length,
      worst: out.slice(0, 14),
    });
  })()`,
  returnByValue: true,
})
console.log(probe.result.value)
if (extra) {
  const r = await send('Runtime.evaluate', { expression: extra, returnByValue: true })
  console.log('EXTRA', typeof r.result.value === 'string' ? r.result.value : JSON.stringify(r.result.value))
}
ws.close()
chrome.kill()
