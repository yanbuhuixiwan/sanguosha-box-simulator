// 按元素裁剪截图：无头 Chrome 只能拍首屏，页面下方区块要靠元素外框 + clip 才能拍全。
// 用法：MOBILE=0 node tools/el_shot.mjs "<login:用户:密码>" "/corridor?period=corr-72" <输出png> [选择器]
//   选择器默认 .board-stage，例如 ".board" 只拍 5×5 阵盘本身。
// 说明：clip 坐标是文档坐标，所以元素 rect 要加上 scrollX/scrollY；captureBeyondViewport 必须开，
// 否则滚出视口的元素会被截成空白。
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = 9351
const BASE = 'http://127.0.0.1:8080'
const [, , spec, pagePath, outFile, sel] = process.argv
if (!spec || !pagePath || !outFile) {
  console.error('args: node tools/el_shot.mjs <login:user:pass> <path> <out.png> [selector]')
  process.exit(1)
}
const selector = sel || '.board-stage'
const profile = path.join(process.env.TEMP || '.', `sgs-el-${Date.now()}`)

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
    } catch {
      /* chrome 还没起来 */
    }
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
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  return r.result.value
}

await send('Page.enable')
await send('Runtime.enable')
const mobile = process.env.MOBILE !== '0'
if (mobile) {
  await send('Emulation.setDeviceMetricsOverride', {
    width: 390, height: 900, deviceScaleFactor: 2, mobile: true,
  })
}
await send('Page.navigate', { url: `${BASE}/login` })
await sleep(1500)

const [user, pass] = spec.replace(/^login:/, '').split(':')
const auth = await evaluate(`fetch('${BASE}/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({username:${JSON.stringify(user)},password:${JSON.stringify(pass)}})})
  .then(r=>r.json()).then(d=>{localStorage.setItem('sgs_token',d.token);return 'ok'}).catch(e=>'fail:'+e.message)`)
if (auth !== 'ok') {
  console.error('登录失败', auth)
  process.exit(1)
}

await send('Page.navigate', { url: `${BASE}${pagePath}${pagePath.includes('?') ? '&' : '?'}t=${Date.now()}` })
await sleep(2600)
await evaluate(`document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({block:'center'}); 'ok'`)
await sleep(600)

const rect = await evaluate(`(() => {
  const el = document.querySelector(${JSON.stringify(selector)});
  if (!el) return '';
  const r = el.getBoundingClientRect();
  return JSON.stringify({ x: r.left + window.scrollX, y: r.top + window.scrollY, w: r.width, h: r.height });
})()`)
if (!rect) {
  console.error('选择器没命中：', selector)
  process.exit(1)
}
const box = JSON.parse(rect)
const { data } = await send('Page.captureScreenshot', {
  format: 'png',
  captureBeyondViewport: true,
  clip: { x: box.x, y: box.y, width: box.w, height: box.h, scale: 2 },
})
fs.mkdirSync(path.dirname(outFile), { recursive: true })
fs.writeFileSync(outFile, Buffer.from(data, 'base64'))
console.log(`✓ ${selector} -> ${outFile}  ${Math.round(box.w)}x${Math.round(box.h)}`)
ws.close()
chrome.kill()
