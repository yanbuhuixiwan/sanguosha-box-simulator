from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..gacha import RARITY_ORDER, pick_many, pity_note, recruit_pool
from ..models import PullRecord, User, get_db
from ..security import current_user
from ..services import add_item, consume_item, get_item, item_qty_by_name, owned_skin_count

router = APIRouter(prefix="/recruit", tags=["招募"])

MAX_PULLS = 10


def _pool_for(pool_id: str, db: Session, user_id: int) -> dict | None:
    """皮肤池要按「已收集款数」解锁分级，武将池不受影响。"""
    owned = owned_skin_count(db, user_id) if pool_id == "skin" else None
    return recruit_pool(pool_id, owned)


@router.get("/{pool_id}")
def get_pool(pool_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pool = _pool_for(pool_id, db, user.id)
    if pool is None:
        raise HTTPException(404, "没有这个招募池")
    owned = item_qty_by_name(db, user.id, pool["cost_item"])
    return {**pool, "owned_cost_item": owned, "max_pulls": MAX_PULLS}


class PullIn(BaseModel):
    count: int = Field(default=1, ge=1)


@router.post("/{pool_id}/pull")
def pull(
    pool_id: str,
    payload: PullIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    pool = _pool_for(pool_id, db, user.id)
    if pool is None:
        raise HTTPException(404, "没有这个招募池")

    if not pool["entries"]:
        raise HTTPException(400, "本期皮肤已全部收集，等下一期吧")

    count = payload.count
    if count > MAX_PULLS:
        raise HTTPException(400, f"一次最多 {MAX_PULLS} 连")

    need = count * pool["cost_per_pull"]
    consume_item(db, user.id, pool["cost_item"], need)

    results = pick_many(pool["entries"], count)

    # 同 key 合并。重复的武将 / 皮肤不再折算将魂、雁翎，照常入袋累加数量，
    # 想换将魂 / 雁翎由玩家在背包里手动分解（见 /inventory/decompose）。
    buckets: dict[str, dict] = {}

    def bump(key: str, name: str, kind: str, rarity: str, qty: int, dup: bool) -> None:
        b = buckets.setdefault(
            key,
            {"key": key, "name": name, "kind": kind, "rarity": rarity, "qty": 0, "dup": 0},
        )
        b["qty"] += qty
        if dup:
            b["dup"] += qty

    for idx, res in enumerate(results):
        res["index"] = idx
        owned = get_item(db, user.id, res["key"])
        is_dup = owned is not None and owned.qty > 0
        res["duplicate"] = is_dup
        res["soul"] = 0
        res["feather"] = 0
        res["note"] = "已拥有，重复卡入背包" if is_dup else None
        add_item(db, user.id, res)
        bump(res["key"], res["name"], res["kind"], res["rarity"], 1, is_dup)

        db.add(
            PullRecord(
                user_id=user.id,
                source=pool_id,
                box_id=None,
                item_key=res["key"],
                name=res["name"],
                kind=res["kind"],
                rarity=res["rarity"],
                qty=1,
                pulls=1,
                cost=pool["cost_per_pull"],
                note=res["note"] if is_dup else None,
            )
        )

    db.add(user)
    db.commit()

    rarity_counts: dict[str, int] = {}
    for res in results:
        rarity_counts[res["rarity"]] = rarity_counts.get(res["rarity"], 0) + 1

    items = sorted(
        buckets.values(), key=lambda x: (RARITY_ORDER.get(x["rarity"], 9), -x["qty"], x["name"])
    )

    payload = {
        "pool_id": pool_id,
        "count": count,
        "cost_item": pool["cost_item"],
        "cost_amount": need,
        "owned_cost_item": item_qty_by_name(db, user.id, pool["cost_item"]),
        "results": results,
        "items": items,
        "duplicate_count": sum(1 for r in results if r["duplicate"]),
        "rarity_counts": rarity_counts,
        "note": pity_note(results),
        "yuanbao": user.yuanbao,
    }
    if pool_id == "skin":
        refresh = _pool_for(pool_id, db, user.id)
        payload.update(
            {
                "owned_skins": refresh["owned_skins"],
                "unlocked_grade": refresh["unlocked_grade"],
                "next_grade_at": refresh["next_grade_at"],
            }
        )
    return payload
