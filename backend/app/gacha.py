"""抽奖核心：权重表、归一化概率、加权随机。

所有概率均由权重推导，绝不硬编码百分比 —— 数值只来自 data/*.json。
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import settings

# 品级：武将 普通/精品/史诗（官方无传说档），皮肤 普通/精良/稀有/史诗/传说，
# 礼盒道具 普通为主、宝珠为史诗
RARITY_ORDER = {"common": 0, "good": 1, "fine": 2, "rare": 3, "epic": 4, "legendary": 5}
RARITY_LABEL = {
    "common": "普通",
    "good": "精品",
    "fine": "精良",
    "rare": "稀有",
    "epic": "史诗",
    "legendary": "传说",
}


def _load(filename: str) -> Any:
    path: Path = settings.DATA_FILES / filename
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def boxes_catalog() -> list[dict]:
    return _load("boxes.json")["boxes"]


@lru_cache(maxsize=8)
def _read_pool(filename: str) -> dict:
    return _load(filename)


def get_box(box_id: str) -> dict | None:
    for box in boxes_catalog():
        if box["id"] == box_id:
            return box
    return None


def box_entries(box: dict) -> list[dict]:
    """把盒子卡池展开成带概率的条目。"""
    # 权重全 0 的坏数据不该让整页 500：兜底成 1，概率算出来是 0，至少能打开
    total = sum(int(e["weight"]) for e in box["pool"]) or 1
    entries = []
    for e in box["pool"]:
        item = dict(e)
        item["kind"] = item.get("kind", "item")
        item["rarity"] = item.get("rarity", "common")
        item["probability"] = round(item["weight"] / total * 100, 4)
        entries.append(item)
    return entries


def unlocked_skin_grade(raw: dict, owned: int) -> tuple[int, int | None]:
    """皮肤收集分级：按「已收集款数」解锁，返回 (当前解锁分级, 下一档所需款数)。"""
    grade, nxt = 1, None
    for item in raw.get("grade_thresholds") or []:
        if owned >= int(item["owned"]):
            grade = int(item["grade"])
        elif nxt is None:
            nxt = int(item["owned"])
    return grade, nxt


def recruit_pool(pool_id: str, owned_skins: int | None = None) -> dict | None:
    """pool_id: hero / skin。返回带归一化概率的卡池。

    owned_skins 只对皮肤池生效：官方「皮肤收集」按已收集款数解锁皮肤分级，
    传入后只保留已解锁分级的条目，并按当前池子重新归一化概率。
    """
    filename = {"hero": "heroes.json", "skin": "skins.json"}.get(pool_id)
    if filename is None:
        return None
    raw = _read_pool(filename)

    kind = "hero" if pool_id == "hero" else "skin"
    name_key = "heroes" if pool_id == "hero" else "skins"

    entries: list[dict] = []
    for tier in raw["tiers"]:
        for row in tier[name_key]:
            if isinstance(row, str):  # 兼容老格式：裸名字 + 整档权重
                row = {"name": row, "weight": int(tier["weight"])}
            entry = {
                "key": f"{kind}:{row['name']}",
                "name": row["name"],
                "kind": kind,
                "rarity": tier["rarity"],
                "weight": int(row["weight"]),
                "tier": tier["level"],
                "tier_label": tier.get("label", ""),
                "grade": row.get("grade"),
                "qty": 1,
            }
            entries.append(entry)

    payload = {
        "pool_id": pool_id,
        "name": raw["name"],
        "cost_item": raw["cost_item"],
        "cost_per_pull": int(raw.get("cost_per_pull", 1)),
        "description": raw.get("description", ""),
        "source": raw.get("source", ""),
        "tiers": raw["tiers"],
        "total_weight": sum(e["weight"] for e in entries),
        "entries": entries,
    }

    if kind == "skin" and owned_skins is not None:
        grade, nxt = unlocked_skin_grade(raw, owned_skins)
        kept = [e for e in entries if int(e["grade"] or 1) <= grade]
        total = sum(e["weight"] for e in kept)
        for e in kept:
            e["probability"] = round(e["weight"] / total * 100, 4)
        payload.update(
            {
                "entries": kept,
                "total_weight": total,
                "unlocked_grade": grade,
                "next_grade_at": nxt,
                "owned_skins": owned_skins,
                "grade_thresholds": raw.get("grade_thresholds") or [],
            }
        )
        return payload

    total = payload["total_weight"]
    for e in entries:
        e["probability"] = round(e["weight"] / total * 100, 4)
    return payload


def skin_pool_exhausted(raw: dict, owned_skins: int) -> bool:
    """已解锁分级里一款不剩（说明该解锁更高一级了）。"""
    grade, _ = unlocked_skin_grade(raw, owned_skins)
    return all(
        int(row.get("grade") or 1) > grade
        for tier in raw["tiers"]
        for row in tier["skins"]
    )


def weighted_pick(entries: list[dict]) -> dict:
    """按 weight 字段做一次加权随机。"""
    total = sum(int(e["weight"]) for e in entries)
    if total <= 0:
        raise ValueError("卡池权重总和必须大于 0")
    roll = random.random() * total
    cursor = 0.0
    for entry in entries:
        cursor += int(entry["weight"])
        if roll < cursor:
            return entry
    return entries[-1]


def pick_many(entries: list[dict], count: int) -> list[dict]:
    return [dict(weighted_pick(entries)) for _ in range(count)]


def pity_note(results: list[dict]) -> str:
    """给整次抽取打个标签，纯展示用。"""
    best = max(results, key=lambda r: RARITY_ORDER.get(r["rarity"], 0))
    if best["rarity"] == "legendary":
        return "欧皇附体"
    if best["rarity"] == "epic":
        return "小有收获"
    return ""


@lru_cache(maxsize=1)
def shop_catalog() -> tuple[dict, ...]:
    """补给商店的售卖清单，价格同样只来自 data/shop.json。"""
    return tuple(_load("shop.json")["items"])


def shop_item(item_key: str) -> dict | None:
    for item in shop_catalog():
        if item["key"] == item_key:
            return dict(item)
    return None


def luck_score(rarity_counts: dict[str, int], pulls: int) -> float:
    """粗糙的欧气值：稀有度加权 / 抽数。"""
    weight = {"common": 1, "good": 2, "fine": 3, "rare": 6, "epic": 20, "legendary": 80}
    score = sum(weight.get(k, 1) * v for k, v in rarity_counts.items())
    return round(score / pulls, 2) if pulls else 0.0


# ---------------------------------------------------------------- 天宫宝库

# 幸运值对大奖权重的加成系数：满值时大奖权重放大 5 倍（0.30% → 约 1.5%）。
PALACE_LUCK_BOOST = 4.0


@lru_cache(maxsize=1)
def _palace_cached(mtime: float) -> dict:
    """palace.json 内容缓存，key 是文件 mtime：改完奖池不用重启后端就能生效。"""
    return _load("palace.json")


def _palace_raw() -> dict:
    path: Path = settings.DATA_FILES / "palace.json"
    return _palace_cached(path.stat().st_mtime)


def palace_periods() -> list[dict]:
    """全部天宫宝库期数（含往期），按时间正序。"""
    return _palace_raw()["periods"]


def current_palace_id() -> str:
    return next(p["id"] for p in palace_periods() if p.get("current"))


def palace_pool(period: str = "") -> dict:
    """返回某期（默认当前期）的完整奖池：共享字段 + 该期大奖与横幅。"""
    raw = _palace_raw()
    pid = period or current_palace_id()
    meta = next((p for p in raw["periods"] if p["id"] == pid), None)
    if meta is None:
        raise KeyError(f"未知的天宫宝库期数: {period}")
    pool = {k: v for k, v in raw.items() if k not in ("periods", "grid")}
    pool.update(meta)
    pool["grid"] = raw["grid"]
    pool["is_current"] = bool(meta.get("current"))
    return pool


def palace_entries(pool: dict, luck: int = 0) -> list[dict]:
    """把 12 格奖池展开成带权重的条目。

    幸运值只放大「大奖格」的权重，普通格不动——这与官方「幸运值越高，
    抽中大奖的概率越高，200 点必中」的描述一致，且总概率仍然归一化。
    """
    limit = int(pool.get("pity_limit", 200)) or 1
    boost = 1.0 + PALACE_LUCK_BOOST * max(0, min(luck, limit)) / limit
    entries: list[dict] = []
    for cell in pool["grid"]:
        entry = dict(cell)
        entry["base_weight"] = int(cell["weight"])
        if entry.get("grand"):
            entry["weight"] = int(round(cell["weight"] * boost))
        entries.append(entry)

    total = sum(int(e["weight"]) for e in entries) or 1
    base_total = sum(int(e["base_weight"]) for e in entries) or 1
    for entry in entries:
        entry["probability"] = round(int(entry["weight"]) / total * 100, 4)
        entry["base_probability"] = round(int(entry["base_weight"]) / base_total * 100, 4)
        if entry.get("grand"):
            entry["candidates"] = pool["grand_prizes"].get(entry["grand"], [])
    return entries


def palace_grand_probability(pool: dict, luck: int = 0) -> float:
    """当前幸运值下「本抽命中任一格大奖」的概率（百分比）。"""
    entries = palace_entries(pool, luck)
    return round(sum(e["probability"] for e in entries if e.get("grand")), 4)


PALACE_GROUP_ORDER = {"普通": 0, "精品": 1, "稀有": 2}


def palace_groups(pool: dict, luck: int = 0) -> list[dict]:
    """按官方公示的三档分类（普通 / 精品 / 稀有）汇总权重与概率。

    官方公示图把 12 格分成 普通 85.00% / 精品 14.70% / 稀有 0.30% 三档，
    这里按 grid 里的 `group` 字段聚合，方便公示页逐档对照。
    """
    buckets: dict[str, dict] = {}
    for entry in palace_entries(pool, luck):
        group = entry.get("group") or ("稀有" if entry.get("grand") else "普通")
        row = buckets.setdefault(
            group, {"group": group, "weight": 0, "probability": 0.0, "cells": 0}
        )
        row["weight"] += int(entry["weight"])
        row["probability"] = round(row["probability"] + entry["probability"], 4)
        row["cells"] += 1
    return sorted(
        buckets.values(), key=lambda r: PALACE_GROUP_ORDER.get(r["group"], 9)
    )


# ---------------------------------------------------------------- 梦之回廊


@lru_cache(maxsize=1)
def _corridor_cached(mtime: float) -> dict:
    """corridor.json 内容缓存，key 是文件 mtime：文件一改缓存自动失效，
    不用重启后端就能看到新的连线奖励 / 奖池。"""
    return _load("corridor.json")


def _corridor_raw() -> dict:
    path = settings.DATA_FILES / "corridor.json"
    return _corridor_cached(path.stat().st_mtime)


def corridor_periods() -> list[dict]:
    return _corridor_raw()["periods"]


def current_corridor_id() -> str:
    return next(p["id"] for p in corridor_periods() if p.get("current"))


def corridor_episode(period: str = "") -> dict:
    """返回某期（默认当前期）的完整梦之回廊：共享字段 + 该期终极大奖。"""
    raw = _corridor_raw()
    pid = period or current_corridor_id()
    meta = next((p for p in raw["periods"] if p["id"] == pid), None)
    if meta is None:
        raise KeyError(f"未知的梦之回廊期数: {period}")
    episode = {k: v for k, v in raw.items() if k not in ("periods", "final_prize")}
    episode.update(
        {
            "id": meta["id"],
            "label": meta["label"],
            "skin": meta["skin"],
            "hero": meta["hero"],
            "dates": meta["dates"],
            "final_prize": meta["final_prize"],
            "is_current": bool(meta.get("current")),
            # 各期碎片概率表与保底抽数不同（官网逐期公示），缺省回落到共享字段
            "fragment_rates": meta.get("fragment_rates") or raw["fragment_rates"],
            "pity_limit": int(meta.get("pity_limit") or raw.get("pity_limit") or 250),
            "table": meta.get("table", ""),
        }
    )
    # 外圈 12 条连线的奖励逐期不同（每期一套排列，个别期某条斜线是皮肤）。
    # 顶层 lines 只是共用模板，这里用该期自己的 line_rewards 逐条覆盖。
    line_rewards = meta.get("line_rewards") or {}
    if line_rewards:
        lines = []
        for line in raw["lines"]:
            line = dict(line)
            reward = line_rewards.get(line["id"])
            if reward:
                line["reward"] = dict(reward)
            lines.append(line)
        # 连线里那一格皮肤跟着该期的对角皮肤走：diag_reward 是唯一真源，
        # 用户补完对角皮肤表后不用重建 line_rewards 也能立刻生效
        diag_reward = meta.get("diag_reward")
        if not diag_reward:
            legacy = meta.get("diag_rewards") or []
            diag_reward = legacy[0] if legacy else None
        if diag_reward:
            for line in lines:
                if line["reward"].get("kind") == "skin":
                    line["reward"] = dict(diag_reward)
        episode["lines"] = lines
    else:
        # 兼容旧数据：只有 diag_reward 时，用它覆盖两条斜线
        diag_reward = meta.get("diag_reward")
        if not diag_reward:
            legacy = meta.get("diag_rewards") or []
            diag_reward = legacy[0] if legacy else None
        if diag_reward:
            lines = []
            for line in raw["lines"]:
                line = dict(line)
                if line["id"].startswith("diag-"):
                    line["reward"] = dict(diag_reward)
                lines.append(line)
            episode["lines"] = lines
    episode["line_template"] = meta.get("line_template", "")
    episode["line_source"] = meta.get("line_source", "")
    return episode


def corridor_draw_entries(episode: dict) -> list[dict]:
    """每次回想抽的那份随机奖励。"""
    entries = [dict(e) for e in episode["draw_pool"]]
    total = sum(int(e["weight"]) for e in entries) or 1
    for entry in entries:
        entry["probability"] = round(int(entry["weight"]) / total * 100, 4)
    return entries


def new_fragment_rate(episode: dict, lit_count: int) -> float:
    """已点亮 lit_count 种碎片时，本次开出「新碎片」的概率（百分比）。

    数值直接来自 corridor.json 的 fragment_rates，与官方公示的五个区间一一对应。
    """
    rates = episode["fragment_rates"]
    if lit_count >= len(rates):
        return 0.0
    return float(rates[max(0, lit_count)])
