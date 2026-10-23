from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import InventoryItem


def get_item(db: Session, user_id: int, item_key: str) -> InventoryItem | None:
    return db.scalar(
        select(InventoryItem).where(
            InventoryItem.user_id == user_id, InventoryItem.item_key == item_key
        )
    )


def add_item(db: Session, user_id: int, entry: dict, qty: int | None = None) -> InventoryItem:
    """入库（同 key 累加）。不 commit，由调用方控制事务。"""
    amount = int(qty if qty is not None else entry.get("qty", 1))
    item = get_item(db, user_id, entry["key"])
    if item is None:
        item = InventoryItem(
            user_id=user_id,
            item_key=entry["key"],
            name=entry["name"],
            kind=entry.get("kind", "item"),
            rarity=entry.get("rarity", "common"),
            qty=amount,
        )
        db.add(item)
        # 立即 flush：否则同一事务里连续入袋同一 key 时会重复 INSERT，
        # 触发 inventory 的唯一约束（批量开盒必踩）。
        db.flush()
    else:
        item.qty += amount
    return item


def consume_item(db: Session, user_id: int, name: str, amount: int, key_candidates: list[str] | None = None) -> str:
    """按 key 或名称消耗道具，返回实际命中的 key。"""
    item = None
    for key in key_candidates or []:
        item = get_item(db, user_id, key)
        if item is not None:
            break
    if item is None:
        item = db.scalar(
            select(InventoryItem)
            .where(InventoryItem.user_id == user_id, InventoryItem.name == name)
            .order_by(InventoryItem.qty.desc())
        )
    if item is None:
        raise HTTPException(402, f"背包中缺少「{name}」")
    if item.qty < amount:
        raise HTTPException(402, f"「{name}」不足，需要 {amount} 个，当前 {item.qty} 个")
    item.qty -= amount
    return item.item_key


def item_qty_by_name(db: Session, user_id: int, name: str) -> int:
    rows = db.scalars(
        select(InventoryItem).where(
            InventoryItem.user_id == user_id, InventoryItem.name == name
        )
    ).all()
    return sum(r.qty for r in rows)


def owned_skin_count(db: Session, user_id: int) -> int:
    """已收集的不同皮肤款数 —— 官方「皮肤收集」用它解锁皮肤分级。"""
    rows = db.scalars(
        select(InventoryItem.item_key).where(
            InventoryItem.user_id == user_id,
            InventoryItem.kind == "skin",
            InventoryItem.qty > 0,
        )
    ).all()
    return len(set(rows))
