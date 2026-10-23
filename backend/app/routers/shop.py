"""补给商店：用元宝直接购买招募令 / 雁翎甲。

卖什么、卖多少钱全部来自 data/shop.json，改价格不用动代码。
购买得到的道具与礼盒掉落的同名道具共用同一个 item_key，因此会自动叠在一格。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..gacha import shop_catalog, shop_item
from ..models import User, get_db
from ..security import current_user
from ..services import add_item, item_qty_by_name

router = APIRouter(prefix="/shop", tags=["商店"])

MAX_BUY = 99


def _serialize(item: dict, owned: int) -> dict:
    return {
        "key": item["key"],
        "name": item["name"],
        "price": int(item["price"]),
        "kind": item.get("kind", "item"),
        "rarity": item.get("rarity", "rare"),
        "tag": item.get("tag", ""),
        "desc": item.get("desc", ""),
        "owned": owned,
    }


@router.get("")
def catalog(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = [
        _serialize(item, item_qty_by_name(db, user.id, item["name"]))
        for item in shop_catalog()
    ]
    return {"items": items, "yuanbao": user.yuanbao, "max_buy": MAX_BUY}


class BuyIn(BaseModel):
    item_key: str = Field(min_length=1)
    count: int = Field(default=1, ge=1, le=MAX_BUY)


@router.post("/buy")
def buy(payload: BuyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = shop_item(payload.item_key)
    if item is None:
        raise HTTPException(404, "商店里没有这件东西")

    count = payload.count
    cost = int(item["price"]) * count
    if user.yuanbao < cost:
        raise HTTPException(
            402,
            f"元宝不足，本次需要 {cost} 元宝，当前 {user.yuanbao} 元宝",
        )

    user.yuanbao -= cost
    db.add(user)

    add_item(db, user.id, item, qty=count)
    db.commit()

    return {
        "key": item["key"],
        "name": item["name"],
        "count": count,
        "unit_price": int(item["price"]),
        "spent": cost,
        "yuanbao": user.yuanbao,
        "owned": item_qty_by_name(db, user.id, item["name"]),
    }
