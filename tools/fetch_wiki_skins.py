#!/usr/bin/env python3
"""给「皮肤」补上官方名字：从哔哩哔哩三国杀移动版 wiki 抓「武将-皮肤名-画师」表，
并把每张皮肤原画按 `武将_皮肤名.jpg` 命名下载。

为什么需要它：官网 hero-detail 页面的皮肤图 alt 全为空，只有序号没有名字；
wiki 的皮肤表是玩家维护的，但字段就是官方皮肤名（与游戏内一致），可与官网素材互补。

用法：
  python tools/fetch_wiki_skins.py --limit 20      # 先试 20 个武将
  python tools/fetch_wiki_skins.py                 # 全部（按 image/官网素材/武将 目录走）
  python tools/fetch_wiki_skins.py --names 灵雎 界严颜
  python tools/fetch_wiki_skins.py --dry-run       # 只抓名单，不下载图

输出：
  image/皮肤图片/<武将>_<皮肤名>.jpg
  image/官网素材/wiki_skins.json   # 武将/皮肤名/画师/品质/来源URL
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "image", "官网素材")
HERO_DIR = os.path.join(OUT, "武将")
SKIN_DIR = os.path.join(ROOT, "image", "皮肤图片")

WIKI = "https://wiki.biligame.com/msgs/"
API = WIKI + "api.php"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"),
    "Referer": WIKI,
    "Accept": "*/*",
}
THUMB_W = 900


def get(url: str, retry: int = 4, timeout: int = 45) -> bytes:
    last = None
    for i in range(retry):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=HEADERS), timeout=timeout).read()
        except Exception as e:  # noqa: BLE001
            last = e
            if "404" in str(e):
                raise
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(f"{url} -> {last}")


def safe(text: str) -> str:
    text = text.replace("·", "").replace("*", "＊")
    return re.sub(r'[\\/:*?"<>|\s]+', "", text)


ROW_RE = re.compile(r'<tr data-row-number="\d+"[^>]*>(.*?)</tr>', re.S)
TITLE_RE = re.compile(r'title="([^"]*\*[^"]*)"')
# 注意：wiki 有些缩略图写成 [[File:xxx.jpg@x350px@center@class=tooltip-content@link=]]，
# 直接取整段会得到不存在的文件名，必须在第一个 @ 处截断。
FILE_RE = re.compile(r'file:([^|\]@]+)', re.I)
BADGE_RE = re.compile(r'class="badge"[^>]*><span>([^<]+)</span>')
PAINTER_RE = re.compile(r'<td class="画师[^"]*">([^<]*)</td>')


def parse_skins(page_html: str) -> list[dict]:
    out = []
    for block in ROW_RE.findall(page_html):
        m = TITLE_RE.search(block)
        if not m:
            continue
        title = htmllib.unescape(m.group(1)).strip()      # 霜刃绚练*灵雎
        if "*" not in title:
            continue
        skin, hero = title.split("*", 1)
        fm = FILE_RE.search(htmllib.unescape(block))
        if not fm:
            continue
        out.append({
            "hero": hero.strip(),
            "skin": skin.strip(),
            "file": fm.group(1).strip(),
            "quality": (BADGE_RE.search(block).group(1).strip() if BADGE_RE.search(block) else ""),
            "painter": (PAINTER_RE.search(block).group(1).strip() if PAINTER_RE.search(block) else ""),
        })
    # 去重（同一皮肤可能多行）
    seen, uniq = set(), []
    for r in out:
        k = (r["hero"], r["skin"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


def resolve_urls(files: list[str]) -> dict[str, str]:
    """批量取图片地址（缩略图宽度 THUMB_W）。"""
    urls: dict[str, str] = {}
    for i in range(0, len(files), 40):
        chunk = files[i:i + 40]
        q = API + "?action=query&format=json&formatversion=2&prop=imageinfo&iiprop=url&iiurlwidth=" \
            + str(THUMB_W) + "&titles=" + urllib.parse.quote("|".join("File:" + f for f in chunk))
        try:
            data = json.loads(get(q).decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  ! imageinfo 失败: {e}")
            continue
        for p in data.get("query", {}).get("pages", []):
            ii = p.get("imageinfo")
            if not ii:
                continue
            urls[p["title"].split(":", 1)[-1]] = ii[0].get("thumburl") or ii[0]["url"]
    return urls


def run(hero_names: list[str], dry: bool, workers: int) -> None:
    os.makedirs(SKIN_DIR, exist_ok=True)
    rows: list[dict] = []
    missing_hero: list[str] = []

    def one(hero: str) -> list[dict]:
        try:
            page = get(WIKI + urllib.parse.quote(hero)).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            return []
        if "皮肤名" not in page:
            return []
        return parse_skins(page)

    print(f"抓取 {len(hero_names)} 个武将的皮肤表…", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(one, h): h for h in hero_names}
        done = 0
        for fut in as_completed(futs):
            hero = futs[fut]
            got = fut.result()
            if not got:
                missing_hero.append(hero)
            rows.extend(got)
            done += 1
            if done % 50 == 0 or done == len(hero_names):
                print(f"  {done}/{len(hero_names)} 位，累计 {len(rows)} 个皮肤", flush=True)

    # 全局去重：同一位武将的同一皮肤可能被多个页面重复列出（如 严颜 出现在 界严颜 页）
    best: dict[tuple[str, str], dict] = {}
    for r in rows:
        k = (r["hero"], r["skin"])
        cur = best.get(k)
        if cur is None or (not cur.get("painter") and r.get("painter")):
            best[k] = r
    rows = list(best.values())

    print(f"共 {len(rows)} 个皮肤（去重后），其中 {len(missing_hero)} 位武将 wiki 无皮肤表")
    if dry:
        json.dump(rows, open(os.path.join(OUT, "wiki_skins.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        for r in rows[:15]:
            print("  ", r["hero"], r["skin"], r["quality"], r["painter"])
        return

    files = sorted({r["file"] for r in rows})
    print(f"解析图片地址 {len(files)} 个…", flush=True)
    urls = resolve_urls(files)

    ok = fail = skipped = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {}
        for r in rows:
            u = urls.get(r["file"])
            if not u:
                r["error"] = "无图片地址"
                fail += 1
                continue
            r["url"] = u
            ext = os.path.splitext(r["file"])[1] or ".jpg"
            target = os.path.join(SKIN_DIR, f'{safe(r["hero"])}_{safe(r["skin"])}{ext}')
            if os.path.exists(target):
                r["path"] = f"皮肤图片/{os.path.basename(target)}"
                skipped += 1
                continue
            futs[pool.submit(lambda uu=u, tt=target: open(tt, "wb").write(get(uu)))] = (r, target)
        for fut in as_completed(futs):
            r, target = futs[fut]
            try:
                fut.result()
                r["path"] = f"皮肤图片/{os.path.basename(target)}"
                ok += 1
            except Exception as e:  # noqa: BLE001
                r["error"] = str(e)[:120]
                fail += 1
            if (ok + fail) % 200 == 0:
                print(f"  下载 {ok + fail}/{len(futs)}…", flush=True)

    json.dump(rows, open(os.path.join(OUT, "wiki_skins.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"完成：新下载 {ok} 张，跳过已存在 {skipped} 张，失败 {fail} 张 -> {SKIN_DIR}")


def repair(workers: int) -> None:
    """给 wiki_skins.json 里「无图片地址」的条目补图。

    早先 FILE_RE 没有截掉缩略图的 @x350px… 参数，导致文件名带脏后缀、
    imageinfo 查不到 → 这些条目被记成失败。修复正则后重跑此模式即可补齐。
    """
    path = os.path.join(OUT, "wiki_skins.json")
    rows = json.load(open(path, encoding="utf-8"))
    bad = []
    for r in rows:
        if r.get("path"):
            continue
        clean = r["file"].split("@", 1)[0].strip()
        if not clean.lower().startswith("file:"):
            r["file"] = clean
        bad.append(r)
    if not bad:
        print("没有待修复条目")
        return
    print(f"待补 {len(bad)} 张，重新解析地址…", flush=True)
    urls = resolve_urls(sorted({r["file"] for r in bad}))
    ok = fail = 0
    for r in bad:
        u = urls.get(r["file"])
        if not u:
            r["error"] = "无图片地址（wiki 无图）"
            fail += 1
            continue
        r["url"] = u
        ext = os.path.splitext(r["file"])[1] or ".jpg"
        target = os.path.join(SKIN_DIR, f'{safe(r["hero"])}_{safe(r["skin"])}{ext}')
        try:
            with open(target, "wb") as fh:
                fh.write(get(u))
            r["path"] = f"皮肤图片/{os.path.basename(target)}"
            r.pop("error", None)
            ok += 1
            print(f"  + {r['hero']}_{r['skin']}", flush=True)
        except Exception as e:  # noqa: BLE001
            r["error"] = str(e)[:120]
            fail += 1
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"修复：成功 {ok} 张，仍无图 {fail} 张")
    for r in rows:
        if not r.get("path"):
            print("   缺:", r["hero"], r["skin"])


def build_owners(workers: int) -> None:
    """生成「武将 → 皮肤清单」归属表（image/官网素材/skin_owners.json）。

    动机：界/势/谋/神/SP 这些版本将，wiki 页面上确实列出了皮肤表，但表格里
    `title` 写的是基础武将名（界关羽页写的是「过关斩将*关羽」）。所以按 `title`
    归类会把它们的皮肤全并到基础将名下，看起来像「界关羽 0 皮肤」。
    这里以「页面属于谁」为准建立归属，图片文件仍复用同一张（不重复占空间）。
    """
    wiki = json.load(open(os.path.join(OUT, "wiki_skins.json"), encoding="utf-8"))
    by_key = {(r["hero"], r["skin"]): r for r in wiki}

    names: set[str] = set()

    def clean(stem: str) -> str:
        for suf in ("_头像", "_2", "_3"):
            if stem.endswith(suf):
                stem = stem[: -len(suf)]
        return stem

    if os.path.isdir(HERO_DIR):
        names |= {clean(d) for d in os.listdir(HERO_DIR)
                  if os.path.isdir(os.path.join(HERO_DIR, d))}
    hero_img = os.path.join(ROOT, "image", "武将图片")
    if os.path.isdir(hero_img):
        names |= {clean(os.path.splitext(f)[0]) for f in os.listdir(hero_img)}
    names |= {r["hero"] for r in wiki}
    names = sorted(n for n in names if n and not n.startswith("."))
    print(f"归属表：扫描 {len(names)} 位武将…", flush=True)

    def one(hero: str) -> tuple[str, list[dict]]:
        try:
            page = get(WIKI + urllib.parse.quote(hero)).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            return hero, []
        if "皮肤名" not in page:
            return hero, []
        return hero, parse_skins(page)

    owners: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (hero, rows) in enumerate(pool.map(one, names), 1):
            lst = []
            for r in rows:
                art = by_key.get((hero, r["skin"])) or by_key.get((r["hero"], r["skin"]))
                lst.append({"skin": r["skin"], "owner": r["hero"],
                            "quality": r["quality"], "painter": r["painter"],
                            "file": (art or {}).get("path", "")})
            owners[hero] = lst
            if i % 100 == 0:
                print(f"  {i}/{len(names)}", flush=True)

    total = sum(len(v) for v in owners.values())
    with_skin = sum(1 for v in owners.values() if v)
    no_art = sum(1 for v in owners.values() for x in v if not x["file"])
    json.dump(owners, open(os.path.join(OUT, "skin_owners.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"归属表：{with_skin}/{len(owners)} 位武将有皮肤，共 {total} 条归属记录，"
          f"其中无对应图片 {no_art} 条 -> {os.path.join(OUT, 'skin_owners.json')}")
    for h in ("界关羽", "势小乔", "界严颜", "严颜"):
        if h in owners:
            print(f"  {h}: {[x['skin'] for x in owners[h]][:6]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="从 wiki 补全皮肤名并按名下载")
    ap.add_argument("--names", nargs="*", help="指定武将；缺省=遍历 官网素材/武将 下所有目录")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 位（调试）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repair", action="store_true", help="只补 wiki_skins.json 里失败的条目")
    ap.add_argument("--owners", action="store_true", help="生成 武将→皮肤 归属表")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    if a.owners:
        build_owners(a.workers)
        return 0
    if a.repair:
        repair(a.workers)
        return 0

    if a.names:
        names = a.names
    else:
        names = sorted(d for d in os.listdir(HERO_DIR) if os.path.isdir(os.path.join(HERO_DIR, d)))
    if a.limit:
        names = names[:a.limit]
    run(names, a.dry_run, a.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
