from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..gacha import RARITY_ORDER, box_entries, boxes_catalog, get_box, pick_many, pity_note
from ..models import PullRecord, User, get_db
from ..security import current_user
from ..services import add_item

router = APIRouter(prefix="/boxes", tags=["盒子"])


@router.get("")
def list_boxes():
    out = []
    for box in boxes_catalog():
        item = {k: v for k, v in box.items() if k != "pool"}
        item["entries"] = sorted(
            box_entries(box), key=lambda e: e["probability"], reverse=True
        )
        item["entry_count"] = len(box["pool"])
        out.append(item)
    return {"boxes": out, "max_bulk_open": settings.MAX_BULK_OPEN}


class OpenIn(BaseModel):
    count: int = Field(default=1, ge=1)


@router.post("/{box_id}/open")
def open_box(
    box_id: str,
    payload: OpenIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    box = get_box(box_id)
    if box is None:
        raise HTTPException(404, "没有这个盒子")

    count = payload.count
    if count > settings.MAX_BULK_OPEN:
        raise HTTPException(400, f"一次最多打开 {settings.MAX_BULK_OPEN} 个盒子")
    if count < 1:
        raise HTTPException(400, "至少打开 1 个")

    cost = box["price"] * count
    if user.yuanbao < cost:
        raise HTTPException(402, f"元宝不足，本次需要 {cost} 元宝，当前 {user.yuanbao} 元宝")

    entries = box_entries(box)
    results = pick_many(entries, count)

    user.yuanbao -= cost

    buckets: dict[str, dict] = {}

    def bucket_of(entry: dict) -> dict:
        return buckets.setdefault(
            entry["key"],
            {
                "name": entry["name"],
                "kind": entry.get("kind", "item"),
                "rarity": entry.get("rarity", "common"),
                "qty": 0,          # 抽中所得（不含附赠）
                "bonus_qty": 0,    # 开盒附赠
                "pulls": 0,
            },
        )

    for idx, res in enumerate(results):
        res["index"] = idx
        add_item(db, user.id, res)
        bucket = bucket_of(res)
        bucket["qty"] += res["qty"]
        bucket["pulls"] += 1

    # 开盒附赠：每开一个盒子固定给一份，不参与权重抽取
    bonus_per_box: list[dict] = []
    for entry in box.get("bonus", []):
        per = int(entry.get("qty", 0))
        if per <= 0:
            continue
        total = per * count
        add_item(db, user.id, entry, qty=total)
        bucket_of(entry)["bonus_qty"] += total
        bonus_per_box.append(
            {
                "key": entry["key"],
                "name": entry["name"],
                "kind": entry.get("kind", "item"),
                "rarity": entry.get("rarity", "common"),
                "qty": per,
                "total": total,
            }
        )

    # 流水只记真实抽取：附赠件的 pulls 为 0，不写记录，避免污染「总抽数」
    for key, b in buckets.items():
        if b["pulls"] <= 0:
            continue
        db.add(
            PullRecord(
                user_id=user.id,
                source="box",
                box_id=box["id"],
                item_key=key,
                name=b["name"],
                kind=b["kind"],
                rarity=b["rarity"],
                qty=b["qty"],
                pulls=b["pulls"],
                cost=box["price"] * b["pulls"],
            )
        )

    db.add(user)
    db.commit()

    rarity_counts: dict[str, int] = {}
    for res in results:
        rarity_counts[res["rarity"]] = rarity_counts.get(res["rarity"], 0) + 1

    # 同 key 的奖励合并成一条（抽中的 + 附赠的算在一起），前端「恭喜获得」按这一份渲染
    items = [
        {
            "key": key,
            "name": b["name"],
            "kind": b["kind"],
            "rarity": b["rarity"],
            "qty": b["qty"] + b["bonus_qty"],
            "drop_qty": b["qty"],
            "bonus_qty": b["bonus_qty"],
            "pulls": b["pulls"],
        }
        for key, b in buckets.items()
    ]
    items.sort(key=lambda x: (RARITY_ORDER.get(x["rarity"], 9), -x["qty"], x["name"]))

    return {
        "box_id": box["id"],
        "box_name": box["name"],
        "count": count,
        "cost": cost,
        "yuanbao": user.yuanbao,
        "results": results,
        "items": items,
        "bonus": bonus_per_box,
        "rarity_counts": rarity_counts,
        "note": pity_note(results),
    }
