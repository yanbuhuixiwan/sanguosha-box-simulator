#!/usr/bin/env python3
"""从《三国杀移动版》官网抓取全部武将原画 / 皮肤原画。

数据来源（官网公开页面，robots.txt 允许抓取，无需登录）：
  1) 武将列表  https://www.sanguosha.cn/pc/hero-list.html
     每个武将 -> https://www.sanguosha.cn/pc/hero-detail-<id>.html
     详情页 <div class="swiper hero-info"> 里：第 1 张是该武将原画，其余是该武将的皮肤图。
     图片有两种写法（新将相对路径 / 老将绝对路径），脚本都认。
  2) 皮肤绘影堂 https://share.sanguosha.cn/api/skins/list?type=<1|2|3>&limit=200
     inner_banner 为 1920x1305 高清横向原画。

命名规则：官方名里的「势·」「界·」「友·」「神」等前缀**必须保留**——
"严颜" 与 "界严颜" 是两名不同武将，"姜维" 与 "神姜维" 也是。脚本只去掉分隔符「·」，
不合并任何前缀；官方列表里同名但 id 不同的（如 孔融/糜夫人/蒋钦）用 _2/_3 后缀区分。

用法：
  python tools/fetch_sgs_assets.py heroes --all               # 全部 588 位（含各自皮肤图）
  python tools/fetch_sgs_assets.py heroes 王凌 阮慧 花鬘        # 指定武将
  python tools/fetch_sgs_assets.py heroes --from-boxes        # 只抓 boxes.json 里出现的
  python tools/fetch_sgs_assets.py skins                      # 绘影堂全部 129 张（约 320MB）
  python tools/fetch_sgs_assets.py skins 心宇同一              # 按皮肤名/武将名过滤
  加 --dry-run 只出清单不下载。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "image", "官网素材")

HERO_LIST = "https://www.sanguosha.cn/pc/hero-list.html"
HERO_DETAIL = "https://www.sanguosha.cn/pc/hero-detail-%d.html"
SKIN_API = "https://share.sanguosha.cn/api/skins/list?type=%d&limit=200"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

ITEM_RE = re.compile(
    r'<a href="https://www\.sanguosha\.cn/pc/hero-detail-(\d+)\.html"[^>]*>\s*'
    r'<div class="general-img"><img src="([^"]+)" alt="([^"]*)"', re.S)
ART_RE = re.compile(
    r'(?:https://www\.sanguosha\.cn)?(/storage/uploads/images/(?:skins/)?\d+\.(?:jpg|png))')


def fetch(url: str, retry: int = 4, timeout: int = 40) -> bytes:
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Referer": "https://www.sanguosha.cn/"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(f"下载失败 {url}: {last}")


def safe_name(text: str) -> str:
    """势·小乔 -> 势小乔：只去分隔符与非法字符，保留全部前缀。"""
    text = text.replace("·", "").replace("*", "＊").replace("／", "_")
    return re.sub(r'[\\/:*?"<>|\s]+', "", text)


def load_heroes() -> dict[str, list[int]]:
    """官方名 -> 该名对应的全部 id（个别武将在官网上有两个 id，如 孔融/蒋钦）。"""
    html = fetch(HERO_LIST).decode("utf-8", "ignore")
    groups: dict[str, set[int]] = {}
    for hid, _thumb, alt in ITEM_RE.findall(html):
        groups.setdefault(alt.strip(), set()).add(int(hid))
    return {k: sorted(v) for k, v in groups.items()}


def roster_from_boxes() -> list[str]:
    path = os.path.join(ROOT, "backend", "app", "data", "boxes.json")
    data = json.load(open(path, encoding="utf-8"))
    boxes = data["boxes"] if isinstance(data, dict) and "boxes" in data else data
    names: list[str] = []
    for b in boxes:
        for it in b.get("pool", []):
            n = (it.get("name") or "").strip()
            if not n or "*" in n or "·" in n or "动态包" in n:
                continue
            if n.endswith("卡") or n in {"欢乐豆", "菜篮子", "将魂", "招募令"}:
                continue
            if it.get("key", "").startswith("hero_") and n not in names:
                names.append(n)
    return names


def grab_hero(ids: list[int], name: str, folder: str, dry: bool) -> dict:
    urls: list[str] = []
    for hid in ids:  # 同名多 id 的情况：把每个 id 的图都收进来
        try:
            html = fetch(HERO_DETAIL % hid).decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {name} id={hid} 页面拉取失败: {e}")
            continue
        for u in ART_RE.findall(html):
            if u.startswith("/"):
                u = "https://www.sanguosha.cn" + u
            if u not in urls:
                urls.append(u)

    entry = {"ids": ids, "name": name, "folder": folder, "files": []}
    if not urls:
        entry["error"] = "官网无原画（详情页图片区为空）"
        return entry

    for i, url in enumerate(urls, 1):
        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".jpg"
        target = os.path.join(OUT_DIR, "武将", folder, f"{folder}_{i}{ext}")
        if not dry:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if not os.path.exists(target):
                open(target, "wb").write(fetch(url))
        entry["files"].append({
            "path": f"武将/{folder}/{folder}_{i}{ext}",
            "kind": "原画" if i == 1 else f"皮肤{i - 1}",
            "url": url,
            "bytes": os.path.getsize(target) if (not dry and os.path.exists(target)) else 0,
        })
    return entry


def grab_skins(wanted: list[str] | None, dry: bool) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for t in (1, 2, 3):
        payload = json.loads(fetch(SKIN_API % t).decode("utf-8"))
        for it in payload["data"]["lists"]["data"]:
            key = f'{it["name"]}＊{it["general"]}'
            if wanted and not any(w in it["name"] or w in it["general"] for w in wanted):
                continue
            if key in seen:
                continue
            seen.add(key)
            rows.append({"key": key, "name": it["name"], "general": it["general"],
                         "label": it["label"], "date": it["pub_time"],
                         "url": it["inner_banner"], "type": t})
    if not dry:
        os.makedirs(os.path.join(OUT_DIR, "皮肤"), exist_ok=True)
    for row in rows:
        target = os.path.join(OUT_DIR, "皮肤", safe_name(row["key"]) + ".jpg")
        row["path"] = f"皮肤/{safe_name(row['key'])}.jpg"
        if dry:
            continue
        if not os.path.exists(target):
            open(target, "wb").write(fetch(row["url"]))
        row["bytes"] = os.path.getsize(target)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="三国杀移动版官网素材抓取")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ph = sub.add_parser("heroes", help="抓武将原画（含该武将的全部皮肤图）")
    ph.add_argument("names", nargs="*")
    ph.add_argument("--from-boxes", action="store_true")
    ph.add_argument("--all", action="store_true")
    ph.add_argument("--dry-run", action="store_true")
    ph.add_argument("--workers", type=int, default=8)

    ps = sub.add_parser("skins", help="抓皮肤绘影堂高清原画")
    ps.add_argument("names", nargs="*")
    ps.add_argument("--dry-run", action="store_true")
    ps.add_argument("--workers", type=int, default=6)

    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    if args.cmd == "skins":
        rows = grab_skins(args.names or None, args.dry_run)
        json.dump(rows, open(os.path.join(OUT_DIR, "skins.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        mb = sum(r.get("bytes", 0) for r in rows) / 1048576
        print(f"皮肤 {len(rows)} 张（{mb:.0f}MB）-> {os.path.join(OUT_DIR, '皮肤')}")
        return 0

    groups = load_heroes()
    by_name: dict[str, list[int]] = {}
    for nm, ids in groups.items():
        by_name[nm] = ids
        by_name[safe_name(nm)] = ids

    if args.all:
        todo = sorted(groups.items(), key=lambda kv: kv[1][0])
    else:
        want = roster_from_boxes() if args.from_boxes else args.names
        if not want:
            print("没有指定武将。用 --all / --from-boxes / 直接列名字")
            return 2
        picked: dict[str, list[int]] = {}
        for n in want:
            ids = by_name.get(n) or by_name.get(safe_name(n))
            if not ids:
                for var in (n.replace("祇", "祗"), n.replace("祗", "祇"), n.replace("祎", "禕")):
                    if var != n and (by_name.get(var) or by_name.get(safe_name(var))):
                        ids = by_name.get(var) or by_name.get(safe_name(var))
                        print(f"  ~ {n} 按官网写法「{var}」命中")
                        break
            if ids:
                picked[n] = ids
            else:
                print(f"  ! {n}: 官网未收录")
        todo = list(picked.items())

    # 目录名保留全部前缀（严颜 / 界严颜 各自独立）；同名不同 id 已合并到同一目录
    jobs: list[tuple[str, list[int], str]] = []
    used: dict[str, int] = {}
    for name, ids in todo:
        base = safe_name(name)
        used[base] = used.get(base, 0) + 1
        folder = base if used[base] == 1 else f"{base}_{used[base]}"
        jobs.append((name, ids, folder))

    print(f"开始抓取 {len(jobs)} 位武将…", flush=True)
    manifest: list[dict] = []
    done = files = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(grab_hero, ids, n, fd, args.dry_run): (n, fd) for n, ids, fd in jobs}
        for fut in as_completed(futs):
            n, fd = futs[fut]
            try:
                entry = fut.result()
            except Exception as e:  # noqa: BLE001
                entry = {"ids": [], "name": n, "folder": fd, "files": [], "error": str(e)}
            manifest.append(entry)
            done += 1
            files += len(entry["files"])
            if done % 25 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)} 位，累计 {files} 张", flush=True)

    manifest.sort(key=lambda e: (e.get("ids") or [9999])[0])
    json.dump(manifest, open(os.path.join(OUT_DIR, "heroes.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    bad = [e for e in manifest if e.get("error")]
    print(f"完成：{len(manifest)} 位 / {files} 张 -> {os.path.join(OUT_DIR, '武将')}")
    if bad:
        print(f"官网无图 {len(bad)} 位：" + "、".join(e["name"] for e in bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
