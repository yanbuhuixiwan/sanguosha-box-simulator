"""天宫宝库：12 格奖池 + 幸运值保底。

规则来源（官网 / 台服同步公告）：
  · 抽奖道具「天工石」100 元宝/颗，单抽 1 颗、十连 10 颗；
  · 奖池 12 格，普通材料可重复，武将大奖 / 造型大奖为本期限定；
  · 每抽 +1 幸运值，幸运值越高大奖概率越高，满 200 点必中；
  · 中大奖后幸运值清零，重复中同一件大奖返还 30 颗天工石。
"""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..gacha import (
    RARITY_ORDER,
    palace_entries,
    palace_grand_probability,
    palace_groups,
    palace_periods,
    palace_pool,
    weighted_pick,
)
from ..models import InventoryItem, PalaceState, PullRecord, User, get_db
from ..security import current_user
from ..services import add_item, consume_item, item_qty_by_name

router = APIRouter(prefix="/palace", tags=["天宫宝库"])

COST_KEY = "stone_ti"


def _pool(period: str = "") -> dict:
    """取某期奖池；期数不存在时给 404，而不是让 KeyError 变成 500。"""
    try:
        return palace_pool(period)
    except (KeyError, StopIteration):
        raise HTTPException(404, "没有这一期天宫宝库")


def _state(db: Session, user_id: int, period: str) -> PalaceState:
    state = db.get(PalaceState, (user_id, period))
    if state is None:
        state = PalaceState(user_id=user_id, period=period, luck=0, pulls=0, jackpots=0)
        db.add(state)
        db.flush()
    return state


def _grand_key(kind: str, name: str) -> str:
    """大奖的背包 key。

    官方公告里同一个武将会有两种写法（「谋法正」/「谋·法正」、「势黄祖」/「势·黄祖」），
    若直接拿名字拼 key，跨期抽到同一件大奖会因为 key 不同而**不触发重复返还**，
    背包里也会出现两条同名记录。这里去掉分隔符做归一。
    """
    plain = name.replace("·", "").replace("*", "").replace("＊", "").replace(" ", "")
    return f"{kind}:{plain}"


def _norm(name: str) -> str:
    """判断「是否已拥有」用的名字归一。

    同一个武将 / 皮肤在不同玩法里的写法不一样：
      · 招募池 / 天宫公告用「谋·张辽」「势·黄祖」，也有不带间隔点的「谋张辽」；
      · 礼盒里皮肤带「动态包」后缀（`流沔洛川·曹植动态包`），天宫公告不带；
      · 礼盒武将的背包 key 是拼音 slug（`hero_mouyujin`），只能按名字比对。
    所以统一去掉分隔符与「动态包」后缀再比。
    """
    plain = name
    for sep in ("·", "*", "＊", " ", "\u3000"):
        plain = plain.replace(sep, "")
    for suffix in ("动态皮肤包", "动态包", "皮肤包"):
        if plain.endswith(suffix) and len(plain) > len(suffix):
            plain = plain[: -len(suffix)]
            break
    return plain


def _owned_names(db: Session, user_id: int, kind: str) -> set[str]:
    """背包里已拥有的某类（hero / skin）物品名，已做归一。"""
    rows = db.execute(
        select(InventoryItem.name).where(
            InventoryItem.user_id == user_id,
            InventoryItem.kind == kind,
            InventoryItem.qty > 0,
        )
    ).all()
    return {_norm(name) for (name,) in rows}


def _grand_owned(owned: dict[str, set[str]], kind: str, name: str) -> bool:
    """是否已拥有该大奖（按归一后的名字判断，跨玩法生效）。"""
    return _norm(name) in owned.get(kind, set())


def _owned_map(db: Session, user_id: int, pool: dict) -> dict[str, list[str]]:
    owned = {kind: _owned_names(db, user_id, kind) for kind in ("hero", "skin")}
    result = {"hero": [], "skin": []}
    for kind, names in pool["grand_prizes"].items():
        for name in names:
            if _grand_owned(owned, kind, name):
                result.setdefault(kind, []).append(name)
    return result


@router.get("")
def state(
    period: str = "",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    pool = _pool(period)
    st = _state(db, user.id, pool["id"])
    db.commit()

    entries = palace_entries(pool, st.luck)
    return {
        **{k: v for k, v in pool.items() if k != "grid"},
        "periods": [
            {
                "id": p["id"], "label": p["label"], "dates": p["dates"],
                "current": bool(p.get("current")),
                "heroes": p["grand_prizes"]["hero"], "skins": p["grand_prizes"]["skin"],
            }
            for p in palace_periods()
        ],
        "entries": entries,
        "groups": palace_groups(pool, st.luck),
        "grand_probability": palace_grand_probability(pool, st.luck),
        "base_grand_probability": palace_grand_probability(pool, 0),
        "max_grand_probability": palace_grand_probability(pool, int(pool["pity_limit"])),
        "luck": st.luck,
        "pulls": st.pulls,
        "jackpots": st.jackpots,
        "owned_cost_item": item_qty_by_name(db, user.id, pool["cost_item"]),
        "grand_owned": _owned_map(db, user.id, pool),
        "yuanbao": user.yuanbao,
    }


class PullIn(BaseModel):
    count: int = Field(default=1, ge=1)
    period: str = ""


@router.post("/pull")
def pull(
    payload: PullIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    pool = _pool(payload.period)
    limit = int(pool["pity_limit"])
    refund = int(pool["repeat_refund"])
    count = payload.count
    if count > int(pool.get("max_pulls", 10)):
        raise HTTPException(400, f"一次最多抽 {pool.get('max_pulls', 10)} 次")

    if not pool.get("is_current"):
        raise HTTPException(400, "往期宝库仅可回看，抽取请在当期进行")

    consume_item(db, user.id, pool["cost_item"], count, key_candidates=[COST_KEY])
    st = _state(db, user.id, pool["id"])

    results: list[dict] = []
    grand_hits: list[dict] = []
    # 一次请求只查两次背包：十连中途抽到的大奖要立刻计入，否则同一轮里
    # 两次抽到同一件大奖时第二次不会触发返还。
    owned = {kind: _owned_names(db, user.id, kind) for kind in ("hero", "skin")}

    for idx in range(count):
        before = st.luck
        # 这一抽之后幸运值就满 200 —— 无论权重如何都必中大奖
        force_grand = before + 1 >= limit
        entries = palace_entries(pool, before)
        picked = dict(weighted_pick(entries))

        if force_grand and not picked.get("grand"):
            picked = dict(random.choice([e for e in entries if e.get("grand")]))

        if picked.get("grand"):
            kind = picked["grand"]
            name = random.choice(pool["grand_prizes"][kind])
            res = {
                "index": idx,
                "key": _grand_key(kind, name),
                "name": name,
                "kind": kind,
                "rarity": "legendary",
                "qty": 1,
                "slot": picked["slot"],
                "grand": kind,
                "pity": force_grand,
                "duplicate": False,
                "refund": 0,
            }
            if _grand_owned(owned, kind, name):
                # 重复大奖折算天工石，与官方一致
                res["duplicate"] = True
                res["refund"] = refund
                add_item(
                    db,
                    user.id,
                    {"key": COST_KEY, "name": pool["cost_item"], "kind": "item", "rarity": "epic"},
                    qty=refund,
                )
            else:
                add_item(db, user.id, res)
                owned[kind].add(_norm(name))
            st.luck = 0
            st.jackpots += 1
            grand_hits.append(res)
        else:
            res = {
                "index": idx,
                "key": picked["key"],
                "name": picked["name"],
                "kind": picked.get("kind", "item"),
                "rarity": picked.get("rarity", "common"),
                "qty": int(picked.get("qty", 1)),
                "slot": picked["slot"],
                "grand": None,
                "pity": False,
                "duplicate": False,
                "refund": 0,
            }
            add_item(db, user.id, res)
            st.luck = before + 1

        st.pulls += 1
        results.append(res)

        # 重复大奖实际到手的是天工石而不是那件大奖，战绩里按「真实入账」记，避免
        # 统计页把返还的天工石也算成抽到的大奖。
        logged = (
            {
                "key": COST_KEY,
                "name": pool["cost_item"],
                "kind": "item",
                "rarity": "epic",
                "qty": res["refund"],
            }
            if res["duplicate"]
            else res
        )
        db.add(
            PullRecord(
                user_id=user.id,
                source="palace",
                box_id=pool["id"],
                item_key=logged["key"],
                name=logged["name"],
                kind=logged["kind"],
                rarity=logged["rarity"],
                qty=logged["qty"],
                pulls=1,
                cost=0,
                note="重复大奖返还天工石" if res["duplicate"] else None,
            )
        )

    db.add(st)
    db.add(user)
    db.commit()

    buckets: dict[str, dict] = {}
    for res in results:
        b = buckets.setdefault(
            res["key"],
            {
                "key": res["key"],
                "name": res["name"],
                "kind": res["kind"],
                "rarity": res["rarity"],
                "qty": 0,
            },
        )
        b["qty"] += res["qty"]

    refund_total = sum(r["refund"] for r in results)
    if refund_total:
        key = COST_KEY
        b = buckets.setdefault(
            key,
            {"key": key, "name": pool["cost_item"], "kind": "item", "rarity": "epic", "qty": 0},
        )
        b["qty"] += refund_total

    items = sorted(
        buckets.values(), key=lambda x: (RARITY_ORDER.get(x["rarity"], 9), -x["qty"], x["name"])
    )

    note = ""
    if grand_hits:
        best = grand_hits[0]
        note = "天命所归" if not best["pity"] else "幸运值圆满"
    elif any(r["rarity"] == "epic" for r in results):
        note = "小有收获"

    return {
        "pool_id": pool["id"],
        "pool_name": f'{pool["name"]} · {pool["label"]}',
        "count": count,
        "cost_amount": count,
        "cost_item": pool["cost_item"],
        "results": results,
        "items": items,
        "grand_hits": grand_hits,
        "refund_total": refund_total,
        "luck": st.luck,
        "pity_limit": limit,
        "pulls": st.pulls,
        "jackpots": st.jackpots,
        "owned_cost_item": item_qty_by_name(db, user.id, pool["cost_item"]),
        "grand_probability": palace_grand_probability(pool, st.luck),
        "note": note,
    }
