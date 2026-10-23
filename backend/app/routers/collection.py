from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..decompose import decompose_reward
from ..gacha import luck_score
from ..models import InventoryItem, PullRecord, User, get_db, iso_utc
from ..security import current_user
from ..services import add_item, get_item

router = APIRouter(tags=["背包与统计"])


@router.get("/inventory")
def inventory(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(InventoryItem)
        .where(InventoryItem.user_id == user.id, InventoryItem.qty > 0)
        .order_by(desc(InventoryItem.qty))
    ).all()

    groups: dict[str, list] = {"item": [], "hero": [], "skin": []}
    for row in rows:
        groups.setdefault(row.kind, []).append(
            {
                "key": row.item_key,
                "name": row.name,
                "kind": row.kind,
                "rarity": row.rarity,
                "qty": row.qty,
                "first_at": iso_utc(row.first_at),
            }
        )

    order = {"legendary": 0, "epic": 1, "rare": 2, "fine": 3, "good": 4, "common": 5}
    for kind in groups:
        groups[kind].sort(key=lambda x: (order.get(x["rarity"], 9), -x["qty"]))

    return {
        "items": groups["item"],
        "heroes": groups["hero"],
        "skins": groups["skin"],
        "total": sum(r.qty for r in rows),
        "hero_count": len(groups["hero"]),
        "skin_count": len(groups["skin"]),
    }


class DecomposeIn(BaseModel):
    key: str
    count: int = Field(default=1, ge=1)


@router.post("/inventory/decompose")
def decompose(
    payload: DecomposeIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """手动分解重复的武将 / 皮肤，换将魂 / 雁翎。

    招募不再自动折算，所以重复卡会以 qty>1 的形式留在背包里；
    这里只允许分解「多出来的」那几份，最后一份始终保留（图鉴还看着呢）。
    """
    item = get_item(db, user.id, payload.key)
    if item is None or item.qty <= 0:
        raise HTTPException(404, "背包里没有这件东西")
    if item.kind not in ("hero", "skin"):
        raise HTTPException(400, "只有武将和皮肤可以分解")
    spare = item.qty - 1
    if spare <= 0:
        raise HTTPException(
            400,
            f"「{item.name}」只剩这一份，分解了就没了，留着吧" if item.kind == "hero"
            else f"「{item.name}」只剩这一款，分解了就没了，留着吧",
        )

    count = min(payload.count, spare)
    reward = decompose_reward(item.kind, item.rarity)
    gained = reward["qty"] * count

    item.qty -= count
    add_item(db, user.id, reward, qty=gained)
    db.commit()

    return {
        "key": item.item_key,
        "name": item.name,
        "kind": item.kind,
        "rarity": item.rarity,
        "decomposed": count,
        "qty": item.qty,
        "gained": {
            "key": reward["key"],
            "name": reward["name"],
            "rarity": reward["rarity"],
            "qty": gained,
        },
    }


# ---------------- 可开启道具 ----------------
# 「一堆银币」这类道具拿到时只是未开启的包裹，玩家在背包里自己点开，
# 开启时才掷出 1000~10000 的银币数量（与游戏内一致）。
OPENABLE = {
    "item:silver_pile": {
        "name": "一堆银币",
        "lo": 1000,
        "hi": 10000,
        "reward": {"key": "silver", "name": "银币", "kind": "item", "rarity": "common"},
    },
}


class OpenIn(BaseModel):
    key: str
    count: int = Field(default=1, ge=1)


@router.post("/inventory/open")
def open_pack(
    payload: OpenIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    spec = OPENABLE.get(payload.key)
    if spec is None:
        raise HTTPException(400, "这个道具不能开启")
    item = get_item(db, user.id, payload.key)
    if item is None or item.qty < payload.count:
        raise HTTPException(402, f"「{spec['name']}」不足，当前 {item.qty if item else 0} 个")

    count = payload.count
    gained = sum(random.randint(int(spec["lo"]), int(spec["hi"])) for _ in range(count))
    item.qty -= count
    add_item(db, user.id, spec["reward"], qty=gained)
    db.commit()

    return {
        "key": item.item_key,
        "name": item.name,
        "opened": count,
        "qty": item.qty,
        "gained": {
            "key": spec["reward"]["key"],
            "name": spec["reward"]["name"],
            "rarity": spec["reward"]["rarity"],
            "qty": gained,
        },
    }


@router.get("/records")
def records(
    limit: int = Query(default=30, ge=1, le=200),
    source: str | None = Query(default=None),
    box_id: str | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(PullRecord).where(PullRecord.user_id == user.id)
    if source:
        stmt = stmt.where(PullRecord.source == source)
    if box_id:
        # 开盒页的「最近获得」只该看这个盒子；不传就是全站流水
        stmt = stmt.where(PullRecord.box_id == box_id)
    rows = db.scalars(stmt.order_by(desc(PullRecord.id)).limit(limit)).all()
    return {
        "records": [
            {
                "id": r.id,
                "source": r.source,
                "box_id": r.box_id,
                "name": r.name,
                "kind": r.kind,
                "rarity": r.rarity,
                "qty": r.qty,
                "pulls": r.pulls,
                "note": r.note,
                "created_at": iso_utc(r.created_at),
            }
            for r in rows
        ]
    }


@router.get("/stats")
def stats(user: User = Depends(current_user), db: Session = Depends(get_db)):
    by_rarity = {
        rarity: qty
        for rarity, qty in db.execute(
            select(PullRecord.rarity, func.sum(PullRecord.pulls))
            .where(PullRecord.user_id == user.id)
            .group_by(PullRecord.rarity)
        ).all()
    }
    by_source = {
        source: qty
        for source, qty in db.execute(
            select(PullRecord.source, func.sum(PullRecord.pulls))
            .where(PullRecord.user_id == user.id)
            .group_by(PullRecord.source)
        ).all()
    }

    total_pulls = sum(by_rarity.values())

    box_stats = []
    for box_id, qty, spent in db.execute(
        select(
            PullRecord.box_id,
            func.sum(PullRecord.pulls),
            func.sum(PullRecord.cost),
        )
        .where(PullRecord.user_id == user.id, PullRecord.source == "box")
        .group_by(PullRecord.box_id)
    ).all():
        box_stats.append({"box_id": box_id, "pulls": qty or 0, "spent": spent or 0})

    # 高光时刻：同一件东西反复出货只留一条（合并数量），否则整块会被一种道具刷屏
    recent = db.scalars(
        select(PullRecord)
        .where(PullRecord.user_id == user.id, PullRecord.rarity.in_(["epic", "legendary"]))
        .order_by(desc(PullRecord.id))
        .limit(120)
    ).all()
    totals: dict[str, int] = {}
    for row in recent:
        key = f"{row.kind}:{row.name}"
        totals[key] = totals.get(key, 0) + (row.qty or 0)
    highlights = []
    seen: set[str] = set()
    for row in recent:
        key = f"{row.kind}:{row.name}"
        if key in seen:
            continue
        seen.add(key)
        highlights.append((row, totals[key]))
        if len(highlights) >= 8:
            break

    since = datetime.now(timezone.utc) - timedelta(days=7)
    daily = []
    for day, qty in db.execute(
        select(func.date(PullRecord.created_at), func.sum(PullRecord.pulls))
        .where(PullRecord.user_id == user.id, PullRecord.created_at >= since)
        .group_by(func.date(PullRecord.created_at))
        .order_by(func.date(PullRecord.created_at))
    ).all():
        daily.append({"date": str(day), "pulls": qty or 0})

    return {
        "total_pulls": total_pulls,
        "by_rarity": by_rarity,
        "by_source": by_source,
        "box_stats": box_stats,
        "highlights": [
            {
                "name": h.name,
                "rarity": h.rarity,
                "kind": h.kind,
                "qty": h.qty,
                "total": total,
                "created_at": iso_utc(h.created_at),
            }
            for h, total in highlights
        ],
        "daily": daily,
        "luck": luck_score(by_rarity, total_pulls),
        "rarity_kinds": len(by_rarity),
        "yuanbao": user.yuanbao,
    }
