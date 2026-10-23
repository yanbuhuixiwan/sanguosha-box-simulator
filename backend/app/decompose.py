"""重复武将 / 重复皮肤的分解规则。

招募令与雁翎甲都**不再自动折算**：抽到的卡一律照常入背包，重复的会累加数量，
想换成将魂 / 雁翎得由玩家在背包里手动分解（只允许分解多出来的那几份，
最后一份留着看图鉴）。

数值：武将沿用官方「普通 1–5 / 精品 10–20 / 史诗 50–100」区间中值；
皮肤官网未公示，按与合成价同量级自定。
"""
from __future__ import annotations

SOUL_KEY = "soul_1000"
SOUL_NAME = "将魂"
FEATHER_KEY = "feather"
FEATHER_NAME = "雁翎"

# 一件重复武将能分解出的将魂
DUP_SOUL = {"common": 3, "good": 15, "epic": 75}
# 一款重复皮肤能分解出的雁翎
DUP_FEATHER = {"common": 100, "fine": 150, "rare": 400, "epic": 1500}


def soul_for(rarity: str) -> int:
    return int(DUP_SOUL.get(rarity, DUP_SOUL["common"]))


def feather_for(rarity: str) -> int:
    return int(DUP_FEATHER.get(rarity, DUP_FEATHER["common"]))


def decompose_reward(kind: str, rarity: str) -> dict:
    """一份重复卡分解后给的东西（entry 形状与背包入库一致）。"""
    if kind == "skin":
        return {
            "key": FEATHER_KEY,
            "name": FEATHER_NAME,
            "kind": "item",
            "rarity": "fine",
            "qty": feather_for(rarity),
        }
    return {
        "key": SOUL_KEY,
        "name": SOUL_NAME,
        "kind": "item",
        "rarity": "epic",
        "qty": soul_for(rarity),
    }
