// 临时截图脚本：用 Chrome headless + CDP 打开本地站点，注入登录态后逐页截图。
// 用法：node tools/shot.mjs <token> <输出目录> <路径1> [路径2 ...]
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = Number(process.env.CDP_PORT || 9333)
const BASE = process.env.BASE || 'http://127.0.0.1:8080'
const token = process.argv[2]
const outDir = process.argv[3]
const pages = process.argv.slice(4)

if (!token || !outDir || !pages.length) {
  console.error('args: node tools/shot.mjs <token> <outDir> <path...>')
  process.exit(1)
}
fs.mkdirSync(outDir, { recursive: true })
const profile = path.join(process.env.TEMP || '.', `sgs-shot-${Date.now()}`)

const chrome = spawn(
  CHROME,
  [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    '--window-size=1440,1000',
    '--hide-scrollbars',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    'about:blank',
  ],
  { stdio: 'ignore' },
)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function targets() {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const list = await res.json()
      const page = list.find((t) => t.type === 'page')
      if (page) return page
    } catch {
      /* chrome 还没起来 */
    }
    await sleep(250)
  }
  throw new Error('chrome 启动超时')
}

const target = await targets()
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  ws.onopen = resolve
  ws.onerror = reject
})

let seq = 0
const pending = new Map()
const events = []
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id)
    pending.delete(msg.id)
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
  } else if (msg.method) {
    events.push(msg)
  }
}

function send(method, params = {}) {
  const id = ++seq
  ws.send(JSON.stringify({ id, method, params }))
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
}

await send('Page.enable')
await send('Runtime.enable')

// MOBILE=1 时按 iPhone 尺寸渲染，用来检查窄屏布局
if (process.env.MOBILE === '1') {
  await send('Emulation.setDeviceMetricsOverride', {
    width: 390,
    height: Number(process.env.MOBILE_H || 844),
    deviceScaleFactor: 2,
    mobile: true,
  })
}

// 先进站点，才能在 localStorage 写入本域 token。
// token 参数支持 "login:用户名:密码"：在页面里调注册接口拿 token，不经过命令行输出。
const loginUrl = `${BASE}/login`
console.log('navigate ->', JSON.stringify(loginUrl))
await send('Page.navigate', { url: loginUrl })
await sleep(1600)

if (token.startsWith('login:')) {
  const [, user, pass] = token.split(':')
  const res = await send('Runtime.evaluate', {
    expression: `fetch('${BASE}/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: ${JSON.stringify(user)}, password: ${JSON.stringify(pass)} }),
      }).then((r) => r.json()).then((d) => {
        // 401 时 fetch 不会 reject，必须显式检查 token，否则会带着 'undefined' 假登录
        if (!d.token) return 'login-failed:' + (d.detail || JSON.stringify(d).slice(0, 80))
        localStorage.setItem('sgs_token', d.token)
        return 'logged-in:' + (d.user ? d.user.nickname : '?')
      }).catch((e) => 'login-failed:' + e.message)`,
    returnByValue: true,
    awaitPromise: true,
  })
  console.log('auth ->', res.result.value)
  if (String(res.result.value).startsWith('login-failed')) process.exit(1)
} else {
  await send('Runtime.evaluate', {
    expression: `localStorage.setItem('sgs_token', ${JSON.stringify(token)}); 'ok'`,
  })
}

for (const spec of pages) {
  // 支持 "/palace|.btn-gold"：导航后点一次该选择器再截图（用来看结算弹窗）
  const [p, selector] = spec.split('|')
  const name = spec.replace(/[^\w]+/g, '_').replace(/^_|_$/g, '') || 'home'
  const sep = p.includes('?') ? '&' : '?'
  const target = `${BASE}${p}${sep}t=${Date.now()}`
  console.log('navigate ->', JSON.stringify(target))
  await send('Page.navigate', { url: target })
  await sleep(2600)
  if (selector) {
    // 支持 "sel1>sel2" 连续点击（例如先进页签，再点卡片上的按钮）
    for (const sel of selector.split('>')) {
      const r = await send('Runtime.evaluate', {
        expression: `(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return 'no-el'; el.click(); return 'clicked'; })()`,
        returnByValue: true,
      })
      if (r.result.value !== 'clicked') console.log(`! 选择器没命中：${sel}`)
      await sleep(1400)
    }
  }
  const errs = events
    .filter((e) => e.method === 'Runtime.exceptionThrown')
    .map((e) => e.params.exceptionDetails.text)
  if (errs.length) console.log(`! ${p} 页面异常：`, errs.slice(-3))
  const { data } = await send('Page.captureScreenshot', {
    format: 'png',
    // 窄屏整页会拉到上万像素，captureBeyondViewport 会把 Chrome 拖死，只拍首屏；
    // 另外它会临时放大视口，导致页面内滚动容器被重置，需要看滚动状态时设 VIEWPORT_ONLY=1
    captureBeyondViewport: process.env.MOBILE !== '1' && process.env.VIEWPORT_ONLY !== '1',
  })
  const file = path.join(outDir, `${name}.png`)
  fs.writeFileSync(file, Buffer.from(data, 'base64'))

  const probe = await send('Runtime.evaluate', {
    expression: `(() => {
      const bad = [...document.images].filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.getAttribute('src'));
      const h1 = (document.querySelector('h1') || {}).innerText || '';
      const st = document.querySelector('.line-row__state');
      let stateBox = null;
      if (st) {
        const r = st.getBoundingClientRect();
        const cs = getComputedStyle(st);
        stateBox = { w: Math.round(r.width), h: Math.round(r.height), ws: cs.whiteSpace, fs: cs.fontSize, text: st.innerText };
      }
      return JSON.stringify({ badImg: bad.slice(0, 6), imgCount: document.images.length, h1: h1.replace(/\s+/g, ' ').trim(), stateBox });
    })()`,
    returnByValue: true,
  })
  console.log(`✓ ${p} -> ${file}`)
  console.log('  ', probe.result.value)
}

ws.close()
chrome.kill()
