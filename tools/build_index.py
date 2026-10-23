#!/usr/bin/env python3
"""为 image/ 下的素材生成一个可搜索的本地索引页与 CSV 清单。

扫描：image/武将图片、image/皮肤图片、image/道具图片
输出：image/index.html、image/素材清单.csv
"""
from __future__ import annotations

import csv
import json
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "image")
GROUPS = ["武将图片", "皮肤图片", "道具图片"]
EXT = {".png", ".jpg", ".jpeg", ".webp"}


def dims(path: str) -> tuple[int, int, str]:
    try:
        im = Image.open(path)
        return im.width, im.height, f"{im.width}×{im.height}"
    except Exception:  # noqa: BLE001
        return 0, 0, "?"


def main() -> None:
    items: list[dict] = []
    rows: list[list] = []
    stat: dict[str, int] = {}

    for g in GROUPS:
        d = os.path.join(IMG, g)
        if not os.path.isdir(d):
            continue
        files = sorted(f for f in os.listdir(d) if os.path.splitext(f)[1].lower() in EXT)
        stat[g] = len(files)
        for f in files:
            p = os.path.join(d, f)
            w, h, size = dims(p)
            stem = os.path.splitext(f)[0]
            if g == "皮肤图片" and "_" in stem:
                hero, skin = stem.split("_", 1)
            elif g == "皮肤图片" and "＊" in stem:
                skin, hero = stem.split("＊", 1)
            else:
                hero, skin = stem, ""
            items.append({"group": g, "name": stem, "hero": hero, "skin": skin,
                          "path": f"{g}/{f}", "size": size, "w": w, "h": h})
            rows.append([g, hero, skin, size, round(os.path.getsize(p) / 1024), f"{g}/{f}"])

    # 同一武将的皮肤排在一起，方便成组浏览
    items.sort(key=lambda it: (GROUPS.index(it["group"]), it["hero"], it["skin"] or it["name"]))
    rows.sort(key=lambda r: (GROUPS.index(r[0]), r[1], r[2]))

    with open(os.path.join(IMG, "素材清单.csv"), "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["分类", "武将", "皮肤名", "分辨率", "大小KB", "相对路径"])
        w.writerows(rows)

    # 皮肤归属表：界/势/谋 等版本将与基础将共用同一张图，这里按「页面属于谁」给出各自清单
    owners_path = os.path.join(IMG, "官网素材", "skin_owners.json")
    if os.path.exists(owners_path):
        owners = json.load(open(owners_path, encoding="utf-8"))
        have = {it["hero"]: it for it in items if it["group"] == "皮肤图片"}
        with open(os.path.join(IMG, "皮肤归属表.csv"), "w", encoding="utf-8-sig", newline="") as fp:
            w = csv.writer(fp)
            w.writerow(["武将", "皮肤数", "皮肤名", "图片文件"])
            for hero, lst in sorted(owners.items(), key=lambda kv: (-len(kv[1]), kv[0])):
                for x in lst:
                    w.writerow([hero, len(lst), x["skin"],
                                x["file"] or f"（缺图）{x['owner']}_{x['skin']}"])
        stat["皮肤归属"] = f"{sum(1 for v in owners.values() if v)}/{len(owners)} 将"
        print(f"  image/皮肤归属表.csv  {sum(len(v) for v in owners.values())} 条")

    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    summary = "　".join(f"{k} {v}" for k, v in stat.items())
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>三国杀素材库</title>
<style>
:root{{--bg:#f6f5f2;--card:#fff;--line:#e3e0da;--ink:#22201d;--sub:#7b756c;--accent:#b3271e}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Microsoft YaHei",system-ui,sans-serif}}
header{{position:sticky;top:0;z-index:9;background:rgba(246,245,242,.95);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line);padding:14px 22px}}
h1{{margin:0 0 6px;font-size:17px;letter-spacing:.5px}}
.meta{{color:var(--sub);font-size:12px;margin-bottom:10px}}
.bar{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
input{{flex:1;min-width:220px;padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;font-size:14px;outline:none}}
input:focus{{border-color:var(--accent)}}
.chip{{padding:6px 12px;border:1px solid var(--line);border-radius:999px;background:#fff;cursor:pointer;font-size:12px;color:var(--sub)}}
.chip.on{{background:var(--accent);border-color:var(--accent);color:#fff}}
main{{padding:18px 22px 60px}}
/* 瀑布流：皮肤横竖版混排时不产生空档 */
.grid{{columns:168px;column-gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;
break-inside:avoid;margin:0 0 14px}}
.card img{{display:block;width:100%;object-fit:cover;background:#eee;cursor:zoom-in}}
.card img.tall{{aspect-ratio:3/4}}
.cap{{padding:7px 9px;font-size:12px;line-height:1.35}}
.cap b{{display:block;font-size:13px}}
.cap span{{color:var(--sub)}}
.cap .h{{color:var(--accent);border-bottom:1px dotted currentColor;cursor:pointer}}
#big{{position:fixed;inset:0;background:rgba(20,18,16,.92);display:none;align-items:center;justify-content:center;z-index:99;padding:30px}}
#big.on{{display:flex}}
#big img{{max-width:94vw;max-height:86vh;box-shadow:0 10px 40px rgba(0,0,0,.5)}}
#big p{{position:absolute;bottom:14px;color:#ddd;font-size:13px}}
</style></head><body>
<header>
  <h1>三国杀素材库</h1>
  <div class="meta" id="meta">{summary}</div>
  <div class="bar">
    <input id="q" placeholder="搜索武将 / 皮肤名，例如 界严颜、采莲江南、霜刃绚练">
    <span class="chip on" data-f="all">全部</span>
    <span class="chip" data-f="武将图片">武将</span>
    <span class="chip" data-f="皮肤图片">皮肤</span>
    <span class="chip" data-f="道具图片">道具</span>
    <span class="chip" id="herochip" hidden></span>
  </div>
</header>
<main><div class="grid" id="grid"></div></main>
<div id="big"><img id="bigimg"><p id="bigcap"></p></div>
<script>
const DATA = {data};
const grid = document.getElementById('grid'), meta = document.getElementById('meta');
const herochip = document.getElementById('herochip');
const HEROES = new Set(DATA.map(it => it.hero).filter(Boolean)).size;
let kw = '', filter = 'all', hero = '';
// 支持 index.html?f=皮肤图片&h=小乔&q=采莲 直接定位
const QS = new URLSearchParams(location.search);
if(QS.get('f')) filter = QS.get('f');
if(QS.get('h')) hero = QS.get('h');
if(QS.get('q')) kw = QS.get('q').toLowerCase();
function match(it){{
  if(filter!=='all' && it.group!==filter) return false;
  if(hero && it.hero!==hero) return false;
  if(!kw) return true;
  return (it.name+' '+it.hero+' '+it.skin).toLowerCase().includes(kw);
}}
function render(){{
  const list = DATA.filter(match);
  grid.innerHTML = list.map(it => {{
    const cls = it.group === '武将图片' ? 'tall' : '';
    return `<div class="card"><img loading="lazy" class="${{cls}}" src="${{encodeURI(it.path)}}"
      onclick="show(this.src,'${{it.name}} · ${{it.size}}')">
      <div class="cap"><b>${{it.skin || it.name}}</b>
      ${{it.skin ? '<span class="h" data-h="'+it.hero+'">'+it.hero+'</span>' : ''}}
      <span> · ${{it.size}}</span></div></div>`;
  }}).join('');
  grid.querySelectorAll('.h').forEach(el => el.onclick = ev => {{
    ev.stopPropagation(); hero = el.dataset.h; render();
  }});
  herochip.hidden = !hero;
  herochip.textContent = hero ? '武将：' + hero + '  ✕' : '';
  meta.textContent = `显示 ${{list.length}} / 共 ${{DATA.length}} 张　${{'{summary}'}}　武将 ${{HEROES}} 位`;
}}
function show(src,cap){{ document.getElementById('bigimg').src=src;
  document.getElementById('bigcap').textContent=cap; document.getElementById('big').classList.add('on'); }}
document.getElementById('big').onclick = e => document.getElementById('big').classList.remove('on');
document.getElementById('q').oninput = e => {{ kw = e.target.value.trim().toLowerCase(); render(); }};
document.querySelectorAll('.chip[data-f]').forEach(c => c.onclick = () => {{
  document.querySelectorAll('.chip[data-f]').forEach(x=>x.classList.remove('on')); c.classList.add('on');
  filter = c.dataset.f; render();
}});
herochip.onclick = () => {{ hero = ''; render(); }};
document.getElementById('q').value = kw;
document.querySelectorAll('.chip[data-f]').forEach(x => x.classList.toggle('on', x.dataset.f === filter));
render();
</script></body></html>"""
    open(os.path.join(IMG, "index.html"), "w", encoding="utf-8").write(html)
    print("image/index.html", len(items), "项", stat)


if __name__ == "__main__":
    main()
