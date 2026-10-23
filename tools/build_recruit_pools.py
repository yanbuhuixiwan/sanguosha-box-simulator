#!/usr/bin/env python3
"""按《三国杀移动版》官方公示重建招募令 / 雁翎甲两个卡池。

数据来源（均为官网公开的概率/权重公示页，无需登录）：
  1) 武将招募权重公示  https://www.sanguosha.cn/news/detail/7.html
     表格：武将名称 / 武将分级(1~20) / 武将招募权重 —— 共 217 名武将。
  2) 皮肤收集权重公示  https://www.sanguosha.cn/news/detail/9.html
     正文里的长图：皮肤名称 / 皮肤分级(1~16) / 皮肤收集权重 —— 共 543 款皮肤。

武将品级官方只给了三档（普通 / 精品 / 史诗），且公示页只给「武将分级 + 权重」。
本脚本用官方给出的三档概率反推分级归属：
  普通 16.56% = 分级 1–5   精品 83.16% = 分级 6–14   史诗 0.29% = 分级 16–20
（与玩家社区公示的 普通 16.54% / 精品 83.17% / 史诗 0.28% 完全吻合，误差来自表格版本差异。）

皮肤品级（普通 / 精良 / 稀有 / 史诗）取自 B 站三国杀移动版 wiki 的皮肤表，
与官方长图相比：分级 1–7 混排 普通+精良，分级 8–9 = 稀有，分级 15–16 = 史诗，可直接校验。

用法：
  python tools/build_recruit_pools.py            # 重建 heroes.json / skins.json
  python tools/build_recruit_pools.py --report   # 只看统计与缺图，不写文件

输出：
  backend/app/data/heroes.json
  backend/app/data/skins.json
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "image", "官网素材")
DATA = os.path.join(ROOT, "backend", "app", "data")

HERO_SRC = os.path.join(OUT, "hero_recruit_official.json")
SKIN_SRC = os.path.join(OUT, "skin_collect_official.txt")
WIKI = os.path.join(OUT, "wiki_skins.json")

# 武将分级 -> 品级（由官方三档概率反推，见文件头说明）
HERO_TIERS = [
    (1, 5, "普通", "common"),
    (6, 14, "精品", "good"),
    (16, 20, "史诗", "epic"),
]

# 皮肤品级 -> 稀有度键 / 排序 / 重复返还雁翎
SKIN_TIERS = [
    ("普通", "common"),
    ("精良", "fine"),
    ("稀有", "rare"),
    ("史诗", "epic"),
]

# 官方面板：拥有皮肤数 -> 解锁的皮肤分级（分级 10~14 官方未启用）
GRADE_THRESHOLDS = [
    (0, 1), (4, 2), (6, 3), (14, 4), (25, 5), (37, 6),
    (60, 7), (70, 8), (84, 9), (98, 15), (117, 16),
]

QUALITY_TO_RARITY = {
    "普通": "common",
    "精良": "fine",
    "稀有": "rare",
    "史诗": "epic",
}


def norm_hero(hero: str) -> str:
    """比对用：去掉「界 / 势 / 友 / 新 / 星 / SP」等前缀。"""
    h = hero.strip()
    for pre in ("界", "势", "友", "新", "星", "SP", "sp"):
        if h.startswith(pre):
            h = h[len(pre):]
    return h


def pretty_hero(hero: str) -> str:
    h = hero.strip()
    return "SP" + h[2:] if h.lower().startswith("sp") else h


def squash(text: str) -> str:
    return text.replace(" ", "").replace("　", "").replace("·", "").replace("＊", "").replace("*", "")


def build_wiki_index(wiki: list[dict]) -> tuple[dict, dict]:
    exact = {}
    by_name = defaultdict(list)
    for row in wiki:
        exact[(row["hero"], row["skin"])] = row
        by_name[row["skin"]].append(row)
    return exact, by_name


def match_wiki(skin: str, hero: str, exact: dict, by_name: dict, names: list[str]) -> dict | None:
    """把官方皮肤名对到 wiki 记录（wiki 会把界将皮肤挂在基础将名下，也有个别错字）。"""
    if (hero, skin) in exact:
        return exact[(hero, skin)]
    for h in (norm_hero(hero), hero):
        if (h, skin) in exact:
            return exact[(h, skin)]
    for row in by_name.get(skin, []):
        if norm_hero(row["hero"]) == norm_hero(hero):
            return row
    for cand in difflib.get_close_matches(skin, names, n=3, cutoff=0.7):
        for row in by_name[cand]:
            if norm_hero(row["hero"]) == norm_hero(hero):
                return row
    # 皮肤名唯一时不必纠结武将写法（官方写「田丘俭 / 严峻」，wiki 写「毌丘俭 / 严畯」）
    same = by_name.get(skin) or []
    if len({row["hero"] for row in same}) == 1:
        return same[0]
    for cand in difflib.get_close_matches(skin, names, n=3, cutoff=0.7):
        for row in by_name[cand]:
            if difflib.SequenceMatcher(None, norm_hero(row["hero"]), norm_hero(hero)).ratio() >= 0.5:
                return row
    return None


def hero_rarity(grade: int) -> tuple[str, str] | None:
    for lo, hi, label, key in HERO_TIERS:
        if lo <= grade <= hi:
            return label, key
    return None


def build_heroes(report: bool) -> dict:
    raw = json.load(open(HERO_SRC, encoding="utf-8"))
    tiers: dict[str, dict] = {}
    labels = [label for _, _, label, _ in HERO_TIERS]
    for row in raw:
        got = hero_rarity(row["grade"])
        if got is None:
            raise SystemExit(f"分级 {row['grade']} 没有对应品级：{row['name']}")
        label, key = got
        tier = tiers.setdefault(
            key,
            {
                "level": labels.index(label) + 1,
                "label": label,
                "rarity": key,
                "heroes": [],
            },
        )
        tier["heroes"].append({"name": row["name"], "grade": row["grade"], "weight": row["weight"]})

    order = [k for _, _, _, k in HERO_TIERS]
    ordered = sorted(tiers.values(), key=lambda t: order.index(t["rarity"]))
    total = sum(h["weight"] for t in ordered for h in t["heroes"])

    for t in ordered:
        t["weight"] = None
        t["note"] = "武将分级 " + "、".join(
            str(g) for g in sorted({h["grade"] for h in t["heroes"]})
        )
        tier_weight = sum(h["weight"] for h in t["heroes"])
        t["probability"] = round(tier_weight / total * 100, 2)
        t["count"] = len(t["heroes"])
        for h in t["heroes"]:
            h["probability"] = round(h["weight"] / total * 100, 4)

    payload = {
        "pool_id": "hero",
        "name": "武将招募",
        "cost_item": "招募令",
        "cost_per_pull": 1,
        "source": "三国杀移动版《武将招募权重公示》（2025-03-11 更新）",
        "description": (
            "消耗招募令招募武将，概率严格取自官方《武将招募权重公示》。"
            "武将品级分普通 / 精品 / 史诗三档，史诗将只在全池里占千分之三左右。"
        ),
        "total_weight": total,
        "tiers": ordered,
    }

    if report:
        print(f"武将 {sum(t['count'] for t in ordered)} 名，总权重 {total}")
        for t in ordered:
            print(
                f"  {t['label']:<3} {t['count']:>3} 名  合计 {t['probability']:>6.2f}%  "
                f"{t['note']}  单件 "
                f"{min(h['probability'] for h in t['heroes']):.3f}%–"
                f"{max(h['probability'] for h in t['heroes']):.3f}%"
            )
    return payload


def build_skins(report: bool) -> dict:
    rows = []
    for line in open(SKIN_SRC, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        skin, hero, grade, weight = line.split("|")
        rows.append(
            {
                "skin": squash(skin),
                "hero": pretty_hero(hero),
                "grade": int(grade),
                "weight": int(weight),
            }
        )

    wiki = json.load(open(WIKI, encoding="utf-8"))
    exact, by_name = build_wiki_index(wiki)
    names = list(by_name)

    tiers: dict[str, dict] = {}
    stat = Counter()
    unmatched = []
    for row in rows:
        found = match_wiki(row["skin"], row["hero"], exact, by_name, names)
        quality = (found or {}).get("quality", "")
        rarity = QUALITY_TO_RARITY.get(quality)
        if rarity is None and quality in ("传说", "限定", "典藏"):
            # wiki 记成传说/限定的个别条目，官方面板里按分级 15/16 归入史诗
            rarity = "epic"
        if rarity is None:
            # wiki 品质留空 / 完全没收录：按官方皮肤分级兜底（8-9 稀有、15-16 史诗，其余普通）
            if row["grade"] >= 15:
                rarity = "epic"
            elif row["grade"] >= 8:
                rarity = "rare"
            else:
                rarity = "common"
            if found is None:
                stat["未收录"] += 1
                unmatched.append(f"{row['skin']}*{row['hero']}(分级{row['grade']})")
            else:
                stat["品质留空"] += 1
        else:
            stat["wiki 品质命中"] += 1

        label = next(l for l, k in SKIN_TIERS if k == rarity)
        tier = tiers.setdefault(
            label,
            {
                "level": [l for l, _ in SKIN_TIERS].index(label) + 1,
                "label": label,
                "rarity": rarity,
                "skins": [],
            },
        )
        name = f"{row['skin']}·{row['hero']}"
        item = {
            "name": name,
            "skin": row["skin"],
            "hero": row["hero"],
            "grade": row["grade"],
            "weight": row["weight"],
        }
        # wiki 的 file 是原始上传名，path 才是本地落盘位置（武将_皮肤名.jpg）
        if found and found.get("path"):
            item["file"] = found["path"]
        tier["skins"].append(item)

    order = [k for _, k in SKIN_TIERS]
    ordered = [t for t in sorted(tiers.values(), key=lambda t: order.index(t["rarity"]))]
    total = sum(s["weight"] for t in ordered for s in t["skins"])

    for t in ordered:
        t["count"] = len(t["skins"])
        t["weight"] = None
        tier_weight = sum(s["weight"] for s in t["skins"])
        t["probability"] = round(tier_weight / total * 100, 2)
        t["note"] = "皮肤分级 " + "、".join(str(g) for g in sorted({s["grade"] for s in t["skins"]}))
        for s in t["skins"]:
            s["probability"] = round(s["weight"] / total * 100, 4)

    payload = {
        "pool_id": "skin",
        "name": "皮肤收集",
        "cost_item": "雁翎甲",
        "cost_per_pull": 1,
        "source": "三国杀移动版《皮肤收集权重公示》（2026-05-15 更新）",
        "description": (
            "消耗雁翎甲收集皮肤，概率取自官方《皮肤收集权重公示》。"
            "已收集皮肤越多，解锁的皮肤分级越高，池子也随之变大；"
            "重复皮肤不折算雁翎，直接留在背包，可手动分解。"
        ),
        "total_weight": total,
        "grade_thresholds": [{"owned": o, "grade": g} for o, g in GRADE_THRESHOLDS],
        "tiers": ordered,
    }

    if report:
        print(f"\n皮肤 {sum(t['count'] for t in ordered)} 款，总权重 {total}")
        for t in ordered:
            print(
                f"  {t['label']:<3} {t['count']:>3} 款  合计 {t['probability']:>6.2f}%  "
                f"{t['note']}  单件 "
                f"{min(s['probability'] for s in t['skins']):.3f}%–"
                f"{max(s['probability'] for s in t['skins']):.3f}%"
            )
        print(
            f"  品质来源：wiki {stat['wiki 品质命中']}，wiki 品质留空 {stat['品质留空']}，"
            f"wiki 未收录 {stat['未收录']}"
        )
        if unmatched:
            print("  未收录清单：" + "、".join(unmatched))
        no_img = [s["name"] for t in ordered for s in t["skins"] if not s.get("file")]
        print(f"  无原画 {len(no_img)} 款" + ("：" + "、".join(no_img[:20]) if no_img else ""))
    return payload


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"  写入 {os.path.relpath(path, ROOT)}  {os.path.getsize(path) // 1024} KB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="只打印统计，不写文件")
    args = ap.parse_args()

    heroes = build_heroes(args.report)
    skins = build_skins(args.report)
    if args.report:
        return
    write_json(os.path.join(DATA, "heroes.json"), heroes)
    write_json(os.path.join(DATA, "skins.json"), skins)
    print("完成。改完记得重跑 tools/build_media_map.py 与前端构建。")


if __name__ == "__main__":
    main()
