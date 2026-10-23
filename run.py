#!/usr/bin/env python
"""三国杀移动版盒子模拟器 · 本地一键启动器

作用：把 Docker Compose 里的两个容器在本地用一个进程复现——
  1. 子进程启动 FastAPI 后端（127.0.0.1:8000）
  2. 主线程启动静态服务（127.0.0.1:8080），托管 frontend/dist 并把 /api 代理到后端
  3. 自动打开浏览器

按 Ctrl+C 或直接关闭窗口即可停止全部服务。
"""

from __future__ import annotations

import http.server
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
DIST_DIR = ROOT / "frontend" / "dist"
DATA_DIR = ROOT / "data"

API_HOST, API_PORT = "127.0.0.1", 8000
WEB_HOST, WEB_PORT = "127.0.0.1", 8080

REQUIRED = "import fastapi, uvicorn, sqlalchemy, jwt"

# 本机回环地址必须绕过系统代理，否则开了 Clash/加速器/公司代理时，
# urllib 会把 http://127.0.0.1:8000 的请求发给代理，导致接口全部 502。
_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def log(msg: str) -> None:
    print(msg, flush=True)


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.35)
        return s.connect_ex((host, port)) == 0


def api_alive(port: int = API_PORT) -> bool:
    try:
        with _LOCAL.open(f"http://{API_HOST}:{port}/api/health", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def pick_python() -> str:
    """挑一个装了后端依赖的解释器：优先项目内 venv，其次当前解释器，最后托管 venv。"""
    candidates = [
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
        Path.home() / ".workbuddy" / "binaries" / "python" / "envs" / "default" / "Scripts" / "python.exe",
    ]
    seen: set[str] = set()
    for exe in candidates:
        key = str(exe).lower()
        if key in seen or not exe.exists():
            continue
        seen.add(key)
        try:
            probe = subprocess.run([str(exe), "-c", REQUIRED], capture_output=True, timeout=30)
            if probe.returncode == 0:
                return str(exe)
        except Exception:
            continue
    return ""


class Handler(http.server.SimpleHTTPRequestHandler):
    server_version = "SGSBox/1.0"
    api_port: int = API_PORT

    def log_message(self, fmt: str, *args) -> None:  # 静音访问日志
        pass

    def end_headers(self) -> None:
        # 每次重新构建后 index.html 引用的 JS/CSS 指纹会变，
        # 若浏览器拿缓存页面就会请求到已删除的资源、显示空白页。
        clean = self.path.split("?", 1)[0].lower()
        if clean in ("", "/") or clean.endswith((".html", ".htm")):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        url = f"http://{API_HOST}:{self.api_port}{self.path}"
        req = urllib.request.Request(url, data=body, method=self.command)
        for header in ("Content-Type", "Authorization", "Accept"):
            value = self.headers.get(header)
            if value:
                req.add_header(header, value)
        try:
            with _LOCAL.open(req, timeout=45) as resp:
                data, status = resp.read(), resp.status
                ctype = resp.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as exc:
            data, status = exc.read(), exc.code
            ctype = exc.headers.get("Content-Type", "application/json")
        except Exception:
            data = json.dumps({"detail": "后端服务未就绪，请稍候重试"}, ensure_ascii=False).encode("utf-8")
            status, ctype = 502, "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _route(self) -> None:
        if self.path.startswith("/api"):
            return self._proxy()
        clean = self.path.split("?", 1)[0].split("#", 1)[0]
        target = DIST_DIR / clean.lstrip("/")
        if clean != "/" and not target.is_file():
            self.path = "/index.html"  # SPA 路由回退
        return super().do_GET()

    do_GET = _route
    do_HEAD = _route
    do_POST = _route
    do_PUT = _route
    do_PATCH = _route
    do_DELETE = _route


def start_backend(python_exe: str, port: int = API_PORT) -> subprocess.Popen:
    env = dict(os.environ)
    env["DATA_DIR"] = str(DATA_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", API_HOST, "--port", str(port)],
        cwd=str(BACKEND_DIR),
        env=env,
    )


def free_port(start: int, tries: int = 20, host: str = WEB_HOST) -> int:
    for port in range(start, start + tries):
        if not port_in_use(host, port):
            return port
    raise SystemExit(f"找不到可用端口（已尝试 {start}-{start + tries - 1}），请先关闭占用这些端口的程序")


def self_check() -> int:
    """一次性体检：解释器 / 依赖 / 前端产物 / 素材 / 端口 / 后端健康。"""
    ok = True

    def line(tag: str, text: str) -> None:
        nonlocal ok
        if tag == "X":
            ok = False
        log(f"[{tag}] {text}")

    log("=" * 58)
    log("  三国杀移动版盒子模拟器 · 环境体检")
    log("=" * 58)
    log(f"项目目录：{ROOT}")
    log(f"系统 Python：{sys.version.split()[0]}  ({sys.executable})")

    exe = pick_python()
    line("OK" if exe else "X", f"可用后端解释器：{exe or '未找到（缺 fastapi/uvicorn/sqlalchemy/pyjwt）'}")

    idx = DIST_DIR / "index.html"
    if idx.is_file():
        line("OK", f"前端产物：{idx}（{idx.stat().st_size} B）")
        html = idx.read_text(encoding="utf-8", errors="ignore")
        refs = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
        missing = [r for r in refs if not (DIST_DIR / r.lstrip("/")).is_file()]
        if not refs:
            line("X", "前端产物里没有引用任何 /assets 资源，构建可能不完整")
        elif missing:
            line("X", f"前端产物引用的 {len(missing)} 个资源缺失：{missing[:3]}（请重新 npm run build）")
        else:
            line("OK", f"前端资源引用完整（{len(refs)} 个 JS/CSS）")
    else:
        line("X", "缺少前端产物 frontend/dist/index.html，请先 npm run build")

    for sub, label in (("武将图片", "武将原画"), ("皮肤图片", "皮肤"), ("道具图片", "道具")):
        d = ROOT / "image" / sub
        n = len([f for f in d.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]) if d.is_dir() else 0
        line("OK" if n else "X", f"素材·{label}：{n} 张（{d}）")

    mm = ROOT / "frontend" / "src" / "assets" / "media-map.json"
    line("OK" if mm.is_file() else "!", f"素材映射表：{'已生成' if mm.is_file() else '未生成，可运行 python tools/build_media_map.py'}")

    line("OK" if DATA_DIR.is_dir() else "!", f"数据目录：{DATA_DIR}")
    db = DATA_DIR / "sanguosha.db"
    line("OK" if db.is_file() else "!", f"数据库：{'已存在 ' + str(db.stat().st_size) + ' B' if db.is_file() else '首次启动时自动创建'}")

    for port, label in ((API_PORT, "后端 API"), (WEB_PORT, "网页入口")):
        used = port_in_use("127.0.0.1", port)
        line("!" if used else "OK", f"端口 {port}（{label}）：{'已被占用，启动时会自动换端口' if used else '空闲'}")

    if api_alive(API_PORT):
        line("OK", f"后端正在运行：http://127.0.0.1:{API_PORT}/api/health")
    else:
        line("!", "后端当前未运行（启动 start.bat 后会拉起）")

    log("-" * 58)
    log("结论：" + ("一切正常，双击 start.bat 即可打开。" if ok else "有问题项（标 X），按提示处理后重试。"))
    return 0 if ok else 1


def main() -> int:
    log("=" * 58)
    log("  三国杀移动版盒子模拟器 · 本地启动")
    log("=" * 58)

    if not DIST_DIR.is_dir() or not (DIST_DIR / "index.html").is_file():
        log("[X] 缺少前端构建产物 frontend/dist/")
        log("    请先在 frontend 目录执行：npm install && npm run build")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    api_port = API_PORT
    backend: subprocess.Popen | None = None
    if api_alive(API_PORT):
        log(f"[1/3] 后端已在 {API_PORT} 端口运行，直接复用")
    else:
        # 8000 被别的程序（常见是上次没关干净的 python）占着时不再直接退出，
        # 自动换一个空闲端口，避免“双击没反应”这种打不开的情况。
        if port_in_use(API_HOST, API_PORT):
            api_port = free_port(API_PORT + 1, 20, API_HOST)
            log(f"[!] {API_PORT} 端口被其他程序占用，后端改用 {api_port}（不影响使用）")
        python_exe = pick_python()
        if not python_exe:
            log("[X] 找不到装有依赖的 Python 解释器")
            log("    请在项目里执行：python -m venv backend/.venv")
            log("    backend/.venv/Scripts/pip install -r backend/requirements.txt")
            return 1
        log(f"[1/3] 启动后端 …  ({python_exe})")
        backend = start_backend(python_exe, api_port)
        for _ in range(120):
            if api_alive(api_port):
                break
            if backend.poll() is not None:
                log("[X] 后端启动失败，请检查上方报错信息")
                return 1
            time.sleep(0.5)
        else:
            log("[X] 后端 60 秒内未就绪")
            backend.terminate()
            return 1
        log(f"      后端就绪 → http://127.0.0.1:{api_port}/api/health")

    Handler.api_port = api_port
    port = free_port(WEB_PORT)
    handler = partial(Handler, directory=str(DIST_DIR))
    try:
        httpd = http.server.ThreadingHTTPServer((WEB_HOST, port), handler)
    except OSError as exc:
        log(f"[X] 无法监听 {port}：{exc}")
        if backend:
            backend.terminate()
        return 1

    # 带上时间戳打开：即使浏览器里还留着旧版 index.html 的缓存，
    # 这个 URL 也是全新的，一定会向本地服务重新取一次页面。
    url = f"http://127.0.0.1:{port}/?t={int(time.time())}"
    log(f"[2/3] 前端服务就绪 → http://127.0.0.1:{port}/")

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    log("[3/3] 已在浏览器打开，若没有自动弹出请手动访问上面的地址")
    log("")
    log("  演示账号可直接在登录页点「注册」新建，初始赠送 8888 元宝")
    log("  按 Ctrl+C 停止服务")
    log("-" * 58)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("\n正在停止 …")
    finally:
        httpd.shutdown()
        httpd.server_close()
        if backend and backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()
        log("已停止，再见。")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv or "check" in sys.argv[1:2]:
        raise SystemExit(self_check())
    raise SystemExit(main())
