#!/usr/bin/env python3
"""把 image/ 下的武将、皮肤、道具图片整理成前端可直接查的映射表。

产出：frontend/src/assets/media-map.json
  { "items": { "招募令": "道具图片/招募令.png", ... },
    "heroes": { "关羽": "武将图片/关羽.jpg", ... },
    "skins": { "关羽_过关斩将": "皮肤图片/关羽_过关斩将.jpg", ... },
    "missing": { "heroes": [...], "skins": [...], "items": [...] } }

为什么要映射而不是直接拼文件名：武将图有 .jpg/.png 两种、皮肤名里带「·」「*」
和「动态包」后缀、异体字（势陈祇/势陈祗）也要能对上，前端不该重复这套规则。

前端通过 /api/media/<相对路径> 取图（后端把 image/ 挂成静态目录）。
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "image")
OUT = os.path.join(ROOT, "frontend", "src", "assets", "media-map.json")
DATA = os.path.join(ROOT, "backend", "app", "data")
EXT = (".jpg", ".jpeg", ".png", ".webp")


def scan(dirname: str) -> dict[str, str]:
    d = os.path.join(IMG, dirname)
    out: dict[str, str] = {}
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(EXT):
            continue
        stem = os.path.splitext(f)[0]
        # 同名多格式时优先 jpg（体积/质量平衡），png 仅在独有时使用
        if stem in out and f.lower().endswith(".png"):
            continue
        out[stem] = f"{dirname}/{f}"
    return out


def parse_skin(name: str) -> tuple[str, str]:
    """「霜刃绚练*灵雎动态包」-> (灵雎, 霜刃绚练)"""
    n = name.replace("动态包", "").strip()
    for sep in ("·", "*", "＊"):
        if sep in n:
            a, b = n.split(sep, 1)
            return b.strip(), a.strip()
    return "", n


def hero_keys(name: str) -> list[str]:
    """官方武将名 -> 可能的落盘文件名（依次尝试，先精确后宽松）。"""
    plain = name.replace("&", "").replace("·", "").replace(" ", "")
    keys = [name, plain]
    if plain.lower().startswith("sp"):
        keys += ["SP" + plain[2:], "sp" + plain[2:]]
    for pre in ("势", "界", "星", "神", "谋"):
        if plain.startswith(pre):
            keys.append(plain[len(pre):])
        else:
            keys += [pre + plain]
    return keys


# 官方表里的写法与落盘名差异较大、规则对不上的，单独列出来
MANUAL_HERO_ALIAS = {"界关张": "关兴张苞"}


def resolve_hero(name: str, heroes: dict[str, str]) -> str:
    for key in hero_keys(name):
        if key in heroes:
            return heroes[key]
    manual = MANUAL_HERO_ALIAS.get(name)
    if manual and manual in heroes:
        return heroes[manual]
    import difflib

    hit = difflib.get_close_matches(name, list(heroes), n=1, cutoff=0.82)
    return heroes[hit[0]] if hit else ""


def main() -> None:
    items = scan("道具图片")
    heroes = scan("武将图片")
    skins_raw = scan("皮肤图片")
    skins = {k: v for k, v in skins_raw.items() if "_" in k}

    # 道具别名：同一个图标下的不同叫法（回廊里的「一堆银币」就是银币图）
    ITEM_ALIAS = {"一堆银币": "银币"}
    for alias_name, base in ITEM_ALIAS.items():
        if base in items and alias_name not in items:
            items[alias_name] = items[base]

    # 卡池里的正式名可能和落盘文件名差一个字（官方写作「平高句丽*田丘俭」，wiki 落盘是「毌丘俭」），
    # skins.json 生成时已经把图片路径算好了，这里把它作为别名补进映射，前端照常按「武将_皮肤名」查。
    skins_data_path = os.path.join(DATA, "skins.json")
    alias = 0
    if os.path.exists(skins_data_path):
        raw_skins = json.load(open(skins_data_path, encoding="utf-8"))
        for tier in raw_skins.get("tiers", []):
            for row in tier.get("skins") or []:
                if not isinstance(row, dict) or not row.get("file"):
                    continue
                rel = row["file"].replace("\\", "/")
                if not os.path.exists(os.path.join(IMG, rel)):
                    continue
                key = f"{row['hero']}_{row['skin']}"
                if key not in skins:
                    skins[key] = rel
                    alias += 1
    if alias:
        print(f"皮肤别名 +{alias}（来自 skins.json 的官方名）")

    # 武将同理：官方名写成「卫温&诸葛直 / SP太史慈 / 董昭」，落盘是「卫温诸葛直 / sp太史慈 / 势董昭」
    heroes_data_path = os.path.join(DATA, "heroes.json")
    hero_alias = 0
    if os.path.exists(heroes_data_path):
        raw_heroes = json.load(open(heroes_data_path, encoding="utf-8"))
        for tier in raw_heroes.get("tiers", []):
            for row in tier.get("heroes") or []:
                name = row["name"] if isinstance(row, dict) else row
                if name in heroes:
                    continue
                got = resolve_hero(name, heroes)
                if got:
                    heroes[name] = got
                    hero_alias += 1
    if hero_alias:
        print(f"武将别名 +{hero_alias}（来自 heroes.json 的官方名）")

    # 天宫宝库各期大奖：皮肤查 wiki_skins 同名条目（「武将_皮肤名」），武将走 resolve_hero
    palace_path = os.path.join(DATA, "palace.json")
    if os.path.exists(palace_path):
        palace = json.load(open(palace_path, encoding="utf-8"))
        wiki_skins = json.load(open(os.path.join(IMG, "官网素材", "wiki_skins.json"), encoding="utf-8"))
        wiki_skins = wiki_skins if isinstance(wiki_skins, list) else wiki_skins.get("skins", [])
        by_skin = {r["skin"]: r for r in wiki_skins}
        pal_hero = pal_skin = 0
        for period in palace.get("periods", []):
            for name in period.get("grand_prizes", {}).get("hero", []):
                if name not in heroes:
                    got = resolve_hero(name, heroes)
                    if got:
                        heroes[name] = got
                        pal_hero += 1
            for name in period.get("grand_prizes", {}).get("skin", []):
                if "·" not in name:
                    continue
                skin_name, hero_name = name.split("·", 1)
                key = f"{hero_name}_{skin_name}"
                if key in skins:
                    continue
                row = by_skin.get(skin_name)
                if row and row.get("path") and row["hero"] == hero_name:
                    rel = row["path"].replace("\\", "/")
                    if os.path.exists(os.path.join(IMG, rel)):
                        skins[key] = rel
                        pal_skin += 1
        print(f"宝库素材：武将 +{pal_hero} · 皮肤 +{pal_skin}")

    # 梦之回廊各期终极大奖皮肤（「皮肤名·武将名」）
    corridor_path = os.path.join(DATA, "corridor.json")
    if os.path.exists(corridor_path):
        corridor = json.load(open(corridor_path, encoding="utf-8"))
        wiki_skins = json.load(open(os.path.join(IMG, "官网素材", "wiki_skins.json"), encoding="utf-8"))
        wiki_skins = wiki_skins if isinstance(wiki_skins, list) else wiki_skins.get("skins", [])
        by_skin = {r["skin"]: r for r in wiki_skins}
        cor = 0
        for period in corridor.get("periods", []):
            skin_name, hero_name = period.get("skin"), period.get("hero")
            if not skin_name or not hero_name:
                continue
            key = f"{hero_name}_{skin_name}"
            if key in skins:
                continue
            row = by_skin.get(skin_name)
            if row and row.get("path") and (row["hero"] == hero_name or row["hero"].replace("·", "") == hero_name.replace("·", "")):
                rel = row["path"].replace("\\", "/")
                if os.path.exists(os.path.join(IMG, rel)):
                    skins[key] = rel
                    cor += 1
        print(f"回廊素材：皮肤 +{cor}")

    # 校验池子里出现的名字都能对上图
    missing = {"items": [], "heroes": [], "skins": []}
    pools: dict[str, set[str]] = {"heroes": set(), "skins": set(), "items": set()}

    def names(rows) -> set[str]:
        return {r["name"] if isinstance(r, dict) else r for r in rows or []}

    boxes_path = os.path.join(DATA, "boxes.json")
    if os.path.exists(boxes_path):
        data = json.load(open(boxes_path, encoding="utf-8"))
        for b in data.get("boxes", []):
            for r in b.get("pool", []) + b.get("bonus", []):
                kind = r.get("kind", "item")
                if kind == "item":
                    pools["items"].add(r["name"])
                elif kind == "hero":
                    pools["heroes"].add(r["name"])
                elif kind == "skin":
                    pools["skins"].add(r["name"])
    for fn, key in (("heroes.json", "heroes"), ("skins.json", "skins")):
        p = os.path.join(DATA, fn)
        if not os.path.exists(p):
            continue
        raw = json.load(open(p, encoding="utf-8"))
        for tier in raw.get("tiers", []):
            pools[key] |= names(tier.get(key))

    for n in sorted(pools["items"]):
        if n not in items:
            missing["items"].append(n)
    for n in sorted(pools["heroes"]):
        if n not in heroes:
            missing["heroes"].append(n)
    for n in sorted(pools["skins"]):
        h, s = parse_skin(n)
        if f"{h}_{s}" not in skins:
            missing["skins"].append(n)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {"items": items, "heroes": heroes, "skins": skins, "missing": missing}
    json.dump(payload, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    print(f"media-map.json  道具 {len(items)} / 武将 {len(heroes)} / 皮肤 {len(skins)}")
    for k, v in missing.items():
        print(f"  缺图 {k}: {len(v)}" + (f" -> {v[:12]}" if v else ""))


if __name__ == "__main__":
    main()
