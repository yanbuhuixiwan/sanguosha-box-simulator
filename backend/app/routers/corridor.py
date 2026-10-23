"""梦之回廊：迷迭珠 → 随机奖励 + 记忆碎片 → 25 格阵盘 12 条连线 → 终极大奖。

规则来源（官网概率公示页 /pc/news-detail-1392.html 等多期公告）：
  · 使用「迷迭珠」获得随机奖励，同时获得 1 个记忆碎片；
  · 阵盘 25 种碎片，不会出现阵盘以外的碎片，可重复点亮；
  · 横向 / 纵向 / 斜向连成直线即领该线奖励，共 12 条线；
  · 集齐 25 种碎片，获得本期终极奖励（传说动态皮肤）；
  · 新碎片概率随累计碎片数递减，五个区间与官方公示一致。
"""

from __future__ import annotations

import json
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


def _line_reward_qty(reward: dict) -> int | None:
    """银币这类随机数量奖励：rand_qty=[lo, hi] 时掷一次随机数。"""
    rand = reward.get("rand_qty")
    if rand:
        return random.randint(int(rand[0]), int(rand[1]))
    return None


from ..gacha import (
    RARITY_ORDER,
    corridor_draw_entries,
    corridor_episode,
    corridor_periods,
    new_fragment_rate,
    weighted_pick,
)
from ..models import CorridorState, PullRecord, User, get_db
from ..security import current_user
from ..services import add_item, consume_item, item_qty_by_name

router = APIRouter(prefix="/corridor", tags=["梦之回廊"])

COST_KEY = "bead_mi"


def _episode(period: str = "") -> dict:
    """取某一期回廊；期数不存在时给 404，而不是让 KeyError 变成 500。"""
    try:
        return corridor_episode(period)
    except (KeyError, StopIteration):
        raise HTTPException(404, "没有这一期梦之回廊")


def _load_ints(raw: str | None) -> list[int]:
    """碎片 id 是整数。"""
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    out: list[int] = []
    for v in value if isinstance(value, list) else []:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _load_strs(raw: str | None) -> list[str]:
    """连线 id 是 "row-1" 这样的字符串，不能走 int()。"""
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def _state(db: Session, user_id: int, period: str) -> CorridorState:
    state = db.get(CorridorState, (user_id, period))
    if state is None:
        state = CorridorState(user_id=user_id, period=period, fragments="[]", lines="[]", pulls=0, finished=0)
        db.add(state)
        db.flush()
    return state


def _board(episode: dict, lit: set[int]) -> list[dict]:
    return [
        {"id": f["id"], "name": f["name"], "lit": f["id"] in lit}
        for f in episode["fragments"]
    ]


@router.get("")
def state(
    period: str = "",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    episode = _episode(period)
    st = _state(db, user.id, episode["id"])
    db.commit()

    lit = set(_load_ints(st.fragments))
    claimed = set(_load_strs(st.lines))
    total = len(episode["fragments"])

    lines = [
        {
            "id": line["id"],
            "label": line["label"],
            "cells": line["cells"],
            "reward": line["reward"],
            "claimed": line["id"] in claimed,
        }
        for line in episode["lines"]
    ]

    return {
        **{
            k: v
            for k, v in episode.items()
            if k not in ("fragments", "lines", "draw_pool", "line_rewards")
        },
        "periods": [
            {
                "id": e["id"], "label": e["label"], "dates": e["dates"],
                "skin": e["skin"], "hero": e["hero"], "current": bool(e.get("current")),
            }
            for e in corridor_periods()
        ],
        "board": _board(episode, lit),
        "lines": lines,
        "draw_entries": corridor_draw_entries(episode),
        "lit_count": len(lit),
        "total_fragments": total,
        "claimed_count": len(claimed),
        "total_lines": len(episode["lines"]),
        "next_new_rate": new_fragment_rate(episode, len(lit)),
        "finished": bool(st.finished),
        "pulls": st.pulls,
        "pity_limit": int(episode.get("pity_limit", 250)),
        "pity_remaining": 0 if st.finished else max(0, int(episode.get("pity_limit", 250)) - st.pulls),
        "owned_cost_item": item_qty_by_name(db, user.id, episode["cost_item"]),
        "yuanbao": user.yuanbao,
    }


class RecallIn(BaseModel):
    count: int = Field(default=1, ge=1)
    period: str = ""


@router.post("/recall")
def recall(
    payload: RecallIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    episode = _episode(payload.period)
    count = payload.count
    max_pulls = int(episode.get("max_pulls", 10))
    if count > max_pulls:
        raise HTTPException(400, f"一次最多回想 {max_pulls} 次")

    st = _state(db, user.id, episode["id"])
    # 25 格集齐后大奖已发，继续回想只会白扣迷迭珠
    if st.finished:
        raise HTTPException(400, "本期 25 格记忆碎片已集齐，终极大奖已发放，不用再回想啦")

    consume_item(db, user.id, episode["cost_item"], count, key_candidates=[COST_KEY])

    lit = set(_load_ints(st.fragments))
    claimed = set(_load_strs(st.lines))
    all_ids = [f["id"] for f in episode["fragments"]]
    entries = corridor_draw_entries(episode)

    draws: list[dict] = []
    fragments: list[dict] = []
    completed: list[dict] = []
    final_won: dict | None = None
    pity = int(episode.get("pity_limit", 250))
    pity_hit = False
    consumed = 0  # 实际抽了几次（保底提前集齐时 < count，差额退珠）

    for idx in range(count):
        # 25 格在上一次（或本次更早的一抽）就集齐了：剩下的次数不再抽，
        # 免得白扣迷迭珠、还在结算里塞一串重复碎片。
        if st.finished:
            break
        item = dict(weighted_pick(entries))
        item["index"] = idx
        # 银币这类随机数量奖励：抽到时掷一次 1000~10000
        rolled = _line_reward_qty(item)
        if rolled is not None:
            item["qty"] = rolled
        add_item(db, user.id, item)
        draws.append(item)

        remaining = [i for i in all_ids if i not in lit]
        rate = new_fragment_rate(episode, len(lit))
        if remaining and random.random() * 100 < rate:
            fid = random.choice(remaining)
            is_new = True
        else:
            # 理论上 lit 为空时上面那支必中（首抽新碎片率 100%）；真走到这里也不能把
            # 碎片「吞掉」——没有旧碎片可重复，只能从剩余里挑一个当新碎片点亮。
            fid = random.choice(sorted(lit)) if lit else random.choice(remaining)
            is_new = fid not in lit
        if is_new:
            lit.add(fid)

        fragments.append(
            {
                "id": fid,
                "name": next(f["name"] for f in episode["fragments"] if f["id"] == fid),
                "is_new": is_new,
                "index": idx,
            }
        )

        # 每次新点亮后检查 12 条连线；本次可能一次连成多条
        for line in episode["lines"]:
            if line["id"] in claimed:
                continue
            if all(cell in lit for cell in line["cells"]):
                claimed.add(line["id"])
                got = _line_reward_qty(line["reward"])
                add_item(db, user.id, line["reward"], qty=got)
                shown = dict(line["reward"])
                if got is not None:
                    shown["qty"] = got
                completed.append(
                    {
                        "id": line["id"],
                        "label": line["label"],
                        "reward": shown,
                        "after_index": idx,
                    }
                )

        # 保底：累计抽数达到本期保底抽数（各期 250 / 500 / 600 抽不同），强制补齐剩余碎片
        if not st.finished and st.pulls + idx + 1 >= pity:
            pity_hit = True
            for fid in [i for i in all_ids if i not in lit]:
                lit.add(fid)
                fragments.append(
                    {
                        "id": fid,
                        "name": next(f["name"] for f in episode["fragments"] if f["id"] == fid),
                        "is_new": True,
                        "index": idx,
                        "pity": True,
                    }
                )
            for line in episode["lines"]:
                if line["id"] in claimed:
                    continue
                claimed.add(line["id"])
                got = _line_reward_qty(line["reward"])
                add_item(db, user.id, line["reward"], qty=got)
                shown = dict(line["reward"])
                if got is not None:
                    shown["qty"] = got
                completed.append(
                    {
                        "id": line["id"],
                        "label": line["label"],
                        "reward": shown,
                        "after_index": idx,
                        "pity": True,
                    }
                )

        # 集齐 25 种碎片 → 终极大奖（只发一次）
        if len(lit) == len(all_ids) and not st.finished:
            prize = episode["final_prize"]
            add_item(db, user.id, prize)
            st.finished = 1
            final_won = dict(prize)

        consumed += 1

    # 保底在十连中途就把 25 格补满时，后面几次没抽——珠子原样退回，抽数也只记实际次数
    refunded = count - consumed
    if refunded > 0:
        add_item(
            db,
            user.id,
            {"key": COST_KEY, "name": episode["cost_item"], "kind": "item", "rarity": "epic"},
            qty=refunded,
        )

    st.pulls += consumed
    st.fragments = json.dumps(sorted(lit))
    st.lines = json.dumps(sorted(claimed))
    db.add(st)
    db.add(user)

    for draw in draws:
        db.add(
            PullRecord(
                user_id=user.id,
                source="corridor",
                box_id=episode["id"],
                item_key=draw["key"],
                name=draw["name"],
                kind=draw.get("kind", "item"),
                rarity=draw.get("rarity", "common"),
                qty=int(draw.get("qty", 1)),
                pulls=1,
                cost=0,
            )
        )

    db.commit()

    # 结算面板：本次随机奖励 + 连线奖励 + 终极大奖，同 key 合并
    buckets: dict[str, dict] = {}

    def bump(entry: dict, qty: int | None = None) -> None:
        b = buckets.setdefault(
            entry["key"],
            {
                "key": entry["key"],
                "name": entry["name"],
                "kind": entry.get("kind", "item"),
                "rarity": entry.get("rarity", "common"),
                "qty": 0,
            },
        )
        b["qty"] += int(qty if qty is not None else entry.get("qty", 1))

    for draw in draws:
        bump(draw)
    for line in completed:
        bump(line["reward"])
    if final_won:
        bump(final_won)

    items = sorted(
        buckets.values(), key=lambda x: (RARITY_ORDER.get(x["rarity"], 9), -x["qty"], x["name"])
    )

    note = ""
    if final_won:
        note = "保底达成" if pity_hit else "回廊圆满"
    elif completed:
        note = "连线得奖"
    elif any(d.get("rarity") == "epic" for d in draws):
        note = "小有收获"

    return {
        "episode_id": episode["id"],
        "episode_name": f"{episode['name']} · {episode['label']}",
        "box_name": f"{episode['name']} · {episode['label']}",
        "count": consumed,
        "requested": count,
        "refunded": refunded,
        "cost_amount": consumed,
        "cost_item": episode["cost_item"],
        "results": draws,
        "items": items,
        "fragments": fragments,
        "new_fragment_ids": [f["id"] for f in fragments if f["is_new"]],
        "lines_completed": completed,
        "final_prize": final_won,
        "board": _board(episode, lit),
        "lit_count": len(lit),
        "total_fragments": len(all_ids),
        "claimed_lines": sorted(claimed),
        "next_new_rate": new_fragment_rate(episode, len(lit)),
        "finished": bool(st.finished),
        "pulls": st.pulls,
        "pity_limit": pity,
        "pity_remaining": 0 if st.finished else max(0, pity - st.pulls),
        "pity_hit": pity_hit,
        "owned_cost_item": item_qty_by_name(db, user.id, episode["cost_item"]),
        "note": note,
    }
