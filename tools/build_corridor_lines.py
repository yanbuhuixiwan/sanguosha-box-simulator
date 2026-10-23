"""按游戏内实拍重建每期外圈的 12 格连线奖励（两套模板）。

背景
----
官网《梦之回廊—XX 概率公示》只公示「碎片奖励（抽取池）」和「新碎片概率」，
不含 12 条连线的奖励；连线奖励只在游戏内 / 小程序阵盘上可见。用户提供了
两张实拍图，逐格核对后得到下面两套模板。

阵盘外圈的几何（7 列 × 6 行）
------------------------------
    右侧第 7 列 = 5 格，对应 5 条横线的奖励（第一行~第五行）
    底部第 6 行 = 7 格：左端 1 格 = 主对角（diag-1）
                          中间 5 格 = 5 条竖线的奖励（第一列~第五列）
                          右端 1 格 = 副对角（diag-2）

模板 A（12 格全是道具）
    第一行 双倍经验卡       第二行 史诗宝珠碎片   第三行 雁翎甲
    第四行 招募令           第五行 雁翎 ×1000
    第一列 将魂 ×100        第二列 进阶丹 ×4      第三列 银币
    第四列 手气卡           第五列 欢乐豆 ×666
    diag-1（左下角） 史诗宝珠
    diag-2（右下角） 菜篮子 ×99

模板 B（11 件道具 + 1 张皮肤）
    第一行 将魂 ×100        第二行 欢乐豆 ×666    第三行 点将卡
    第四行 换将卡           第五行 手气卡
    第一列 史诗宝珠碎片     第二列 雁翎 ×1000     第三列 心愿积分
    第四列 雁翎甲           第五列 进阶丹 ×4
    diag-1（左下角） 该期对角皮肤
    diag-2（右下角） 史诗宝珠

其余各期没有实拍图，按期号做确定性分配（同一期永远得到同一套），
`line_source` 标明来源：screenshot / inferred。以后拿到某一期的截图，
把该期写进 SCREENSHOTS 再跑一遍即可覆盖。

用法
----
    python tools/build_corridor_lines.py            # 写入 corridor.json
    python tools/build_corridor_lines.py --report   # 只看分配结果
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend" / "app" / "data" / "corridor.json"

# 连线奖励用到的道具：(名称, 数量, 稀有度)
# 用户明确给出数量的按实拍填；截图上看不到数量的按游戏常见档位取，
# 想改直接动这里再跑一遍即可。
POOL = {
    "exp": ("双倍经验卡", 1, "rare"),
    "shard": ("史诗宝珠碎片", 1, "epic"),
    "armor": ("雁翎甲", 1, "rare"),
    "recruit": ("招募令", 1, "rare"),
    "feather": ("雁翎", 1000, "common"),
    "soul": ("将魂", 100, "epic"),
    "pill": ("进阶丹", 4, "common"),
    # 银币数量随机：打开获得 1000~10000，qty=0 表示不显示固定数量角标
    "coin": ("银币", 0, "common"),
    "luck": ("手气卡", 1, "common"),
    "bean": ("欢乐豆", 666, "common"),
    "orb": ("史诗宝珠", 1, "epic"),
    "basket": ("菜篮子", 99, "common"),
    "pick": ("点将卡", 5, "common"),
    "swap": ("换将卡", 3, "common"),
    "heart": ("心愿积分", 200, "common"),
}

# 银币的随机数量区间（游戏内实拍：打开获得 1000-10000 银币）
COIN_RAND = (1000, 10000)

# 12 条线在阵盘外圈的固定顺序：右列 5 条横线 → 底部 5 条竖线 → 两条斜线
SLOT_IDS = [
    "row-1", "row-2", "row-3", "row-4", "row-5",
    "col-1", "col-2", "col-3", "col-4", "col-5",
    "diag-1", "diag-2",
]

# 实拍模板：键是线 id，值是道具 key（"skin" = 用本期对角皮肤占这一格）
TEMPLATE_A = {
    "row-1": "exp", "row-2": "shard", "row-3": "armor", "row-4": "recruit", "row-5": "feather",
    "col-1": "soul", "col-2": "pill", "col-3": "coin", "col-4": "luck", "col-5": "bean",
    "diag-1": "orb", "diag-2": "basket",
}
TEMPLATE_B = {
    "row-1": "soul", "row-2": "bean", "row-3": "pick", "row-4": "swap", "row-5": "luck",
    "col-1": "shard", "col-2": "feather", "col-3": "heart", "col-4": "armor", "col-5": "pill",
    "diag-1": "skin", "diag-2": "orb",
}

# 已拿到实拍图、按图对齐的期数（corr-76 势国渊期实拍 2026-09-30，corr-77 许攸期实拍）
SCREENSHOTS = {
    "corr-77": "A",
    "corr-08": "B",
    "corr-76": "B",
}

LABELS = {
    "row-1": "第一行", "row-2": "第二行", "row-3": "第三行", "row-4": "第四行", "row-5": "第五行",
    "col-1": "第一列", "col-2": "第二列", "col-3": "第三列", "col-4": "第四列", "col-5": "第五列",
    "diag-1": "主对角", "diag-2": "副对角",
}


def item_reward(key: str) -> dict:
    name, qty, rarity = POOL[key]
    r = {"key": f"line:{name}", "name": name, "kind": "item", "rarity": rarity, "qty": qty}
    if key == "coin":
        r["rand_qty"] = list(COIN_RAND)
    return r


def skin_reward(meta: dict) -> dict | None:
    """该期对角皮肤（diag_reward），旧数据回落到 diag_rewards[0]。"""
    r = meta.get("diag_reward")
    if not r:
        legacy = meta.get("diag_rewards") or []
        r = legacy[0] if legacy else None
    return dict(r) if r else None


def pick_template(meta: dict) -> str:
    """所有期统一用许攸期实拍布局（模板 A）：横线 双倍经验卡 / 史诗宝珠碎片 /
    雁翎甲 / 招募令×2 / 雁翎×1000；竖线 将魂×100 / 进阶丹×4 / 银币(1000~10000
    随机) / 手气卡×5 / 欢乐豆×666；左下史诗宝珠、右下菜篮子×99。无对应道具图标
    的期也一律按这套显示。"""
    return "A"


def build_line_rewards(meta: dict, tpl: str) -> dict:
    table = TEMPLATE_A if tpl == "A" else TEMPLATE_B
    out = {}
    for line_id in SLOT_IDS:
        key = table[line_id]
        if key == "skin":
            reward = skin_reward(meta) or item_reward("basket")
        else:
            reward = item_reward(key)
        out[line_id] = reward
    return out


def main() -> None:
    import sys

    report = "--report" in sys.argv
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    stat = {"A": 0, "B": 0}
    for meta in raw["periods"]:
        tpl = pick_template(meta)
        stat[tpl] += 1
        meta["line_rewards"] = build_line_rewards(meta, tpl)
        meta["line_template"] = tpl
        meta["line_source"] = "screenshot" if meta["id"] in SCREENSHOTS else "inferred"
        if report:
            marks = "实拍" if meta["line_source"] == "screenshot" else "推定"
            print(f"{meta['id']:>8} {meta['label']:<6} {meta['hero']:<6} 模板{tpl}  {marks}")

    # 顶层 lines 只是兜底模板（该期没有 line_rewards 时用），同步成模板 A
    fallback = build_line_rewards({"id": "corr-77", "diag_reward": None}, "A")
    for line in raw["lines"]:
        if line["id"] in fallback:
            line["reward"] = fallback[line["id"]]

    if report:
        print(f"\n合计：模板A {stat['A']} 期 / 模板B {stat['B']} 期")
        return

    DATA.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {DATA}：模板A {stat['A']} 期 / 模板B {stat['B']} 期")


if __name__ == "__main__":
    main()
