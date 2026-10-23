"""补齐 corridor.json 里缺失的期次（数据源：tools/corridor_official.json）。

背景
----
`tools/build_corridor.py` 会按官方清单整表重建 `periods`，但它不管人工维护的
`diag_reward` / `line_rewards` / `line_template`，所以不能随便重跑来补期——那样
会把 65 期实拍连线和逐期对角皮肤全部冲掉。这个脚本只做「插入缺失期」：
已有的期一个字段都不动，只把官方清单里有、`corridor.json` 里没有的期按下面
规则补出来，插入到按日期排好的位置。

缺失期的字段怎么来
------------------
· `id`        —— 该期在官方清单（按日期升序）里的序号，`corr-NN`
· `table` / `fragment_rates` / `pity_limit` —— 与 build_corridor.py 同一套档位表
· `final_prize` —— 期名·武将，传说动态皮肤
· `diag_reward` —— 先查 `CONFIRMED_LAYOUT`（有整圈实拍、能确认对角皮肤的期）；
                  没有就按 patch_corridor_diag.py 的规则推定（往前 2 期的大奖；
                  往前不够就改取往后 2 期），标 `line_source: inferred`
· `line_rewards` —— 有整圈实拍的期按实拍逐格铺（`CONFIRMED_LAYOUT` 的 side /
                  bottom / diag2）；其余用模板 A 的 10 条直线 + 两条斜线照抄实拍
                  里最常见的形态（主对角放该期的对角皮肤、副对角放菜篮子 ×99）

用法
----
    python tools/repair_corridor_periods.py            # 只报告缺哪些期
    python tools/repair_corridor_periods.py --write     # 补进去并写回
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend" / "app" / "data" / "corridor.json"
OFFICIAL = ROOT / "tools" / "corridor_official.json"

sys.path.insert(0, str(ROOT / "tools"))
from build_corridor import HEAD_RATES, PITY, RATE_TABLES  # noqa: E402
from build_corridor_lines import build_line_rewards, item_reward, pick_template  # noqa: E402


# 「一堆银币」包裹：拿到后在背包里开启，掷出 1000~10000 银币
SILVER_PILE = {
    "key": "item:silver_pile",
    "name": "一堆银币",
    "kind": "item",
    "rarity": "common",
    "qty": 1,
}


def official_sorted() -> list[dict]:
    rows = json.loads(OFFICIAL.read_text(encoding="utf-8"))
    return sorted(rows, key=lambda r: r["date"])


# 已拿到游戏内实拍、能确认整圈 12 格的期。键是期名，值取自 POOL 的 key：
#   side   —— 右侧竖列，从上到下（前端 row-1..5）
#   bottom —— 底部横排，从左到右（前端 col-1..5）
#   diag / diag2 —— 左下角皮肤、右下角奖励
# "pile" 表示「一堆银币」包裹（item:silver_pile），不是直接发随机银币。
# 没有实拍的期仍按模板 A + 推定对角皮肤补齐。
CONFIRMED_LAYOUT = {
    # corr-02 匡汉延祚期（2023-12-15）实拍：左下角是邓艾「袭蜀神兵」，
    # 竖列从上到下是一堆银币 / 招募令 / 将魂 / 雁翎甲 / 进阶丹，
    # 底行从左到右是欢乐豆 / 史诗宝珠碎片 / 双倍经验卡 / 手气卡 / 雁翎，右下角菜篮子。
    "匡汉延祚": {
        "diag": "袭蜀神兵·邓艾",
        "side": ["pile", "recruit", "soul", "armor", "pill"],
        "bottom": ["bean", "shard", "exp", "luck", "feather"],
        "diag2": "basket",
    },
}


def diag_of(periods: list[dict], idx: int) -> dict:
    """对角皮肤：有实拍就用 CONFIRMED_LAYOUT，否则推定「往前 2 期大奖」
    （往前不够就改取往后 2 期，与 patch_corridor_diag.py 一致）。"""
    layout = CONFIRMED_LAYOUT.get(periods[idx]["label"])
    if layout:
        known = layout["diag"]
        return {"key": f"skin:{known}", "name": known, "kind": "skin", "rarity": "legendary", "qty": 1}
    total = len(periods)
    j = idx - 2
    if j < 0:
        j = idx + 2
    if j >= total:
        j %= total
    skin = dict(periods[j]["final_prize"])
    skin["qty"] = 1
    return skin


def _reward(key: str) -> dict:
    """池 key → 奖励字典；"pile" 表示「一堆银币」包裹。"""
    return SILVER_PILE.copy() if key == "pile" else item_reward(key)


def apply_confirmed(new: dict, layout: dict) -> None:
    """按实拍铺满外圈 12 格（竖列 + 底行 + 两角）。"""
    lr = new["line_rewards"]
    for i, key in enumerate(layout["side"], start=1):
        lr[f"row-{i}"] = _reward(key)
    for i, key in enumerate(layout["bottom"], start=1):
        lr[f"col-{i}"] = _reward(key)
    lr["diag-1"] = dict(new["diag_reward"])
    lr["diag-2"] = _reward(layout.get("diag2", "basket"))
    new["line_template"] = "custom"
    new["line_source"] = "screenshot"


def make_period(row: dict, pid: str) -> dict:
    table = row["table"]
    return {
        "id": pid,
        "label": row["name"],
        "skin": row["name"],
        "hero": row["hero"],
        "dates": row["date"],
        "table": table,
        "fragment_rates": HEAD_RATES + RATE_TABLES[table],
        "pity_limit": PITY[table],
        "final_prize": {
            "key": f"skin:{row['name']}·{row['hero']}",
            "name": f"{row['name']}·{row['hero']}",
            "kind": "skin",
            "rarity": "legendary",
            "qty": 1,
        },
        "current": False,
    }


def main() -> None:
    write = "--write" in sys.argv
    data = json.loads(DATA.read_text(encoding="utf-8"))
    periods: list[dict] = data["periods"]
    official = official_sorted()

    have = {(p["label"], p["hero"]) for p in periods}
    missing = [
        (f"corr-{i:02d}", row)
        for i, row in enumerate(official, start=1)
        if (row["name"], row["hero"]) not in have
    ]
    print(f"corridor.json 现有 {len(periods)} 期，官方清单 {len(official)} 期")

    used_ids = {p["id"] for p in periods}
    for pid, row in missing:
        note = "" if pid not in used_ids else f"  !! id {pid} 已被占用，改用 {row['date']}"
        print(f"  缺 {pid}  {row['date']}  {row['name']}·{row['hero']}（表 {row['table']}）{note}")
    if not missing:
        print("没有缺失期，无需处理。")
        return
    if not write:
        print("\n（只报告，加 --write 才会写入）")
        return

    for pid, row in missing:
        new = make_period(row, pid)
        # diag_reward / line_rewards 要按插入后的完整序列算，先插进去再补
        periods.append(new)
        periods.sort(key=lambda p: p["dates"])
        idx = periods.index(new)
        new["diag_reward"] = diag_of(periods, idx)
        tpl = pick_template(new)
        new["line_rewards"] = build_line_rewards(new, tpl)
        layout = CONFIRMED_LAYOUT.get(new["label"])
        if layout:
            # 有整圈实拍：12 格全按图铺，不用模板
            apply_confirmed(new, layout)
        else:
            # 模板 A 的主对角本来是「史诗宝珠」；实拍里这里放的是该期对角皮肤
            new["line_rewards"]["diag-1"] = dict(new["diag_reward"])
            # 模板里的「银币」是直接发 1000~10000 银币；但另外 76 期发的都是
            # 「一堆银币」包裹（背包里自己开，见 collection.OPENABLE），这里跟随多数派
            for lid, reward in new["line_rewards"].items():
                if reward.get("rand_qty"):
                    new["line_rewards"][lid] = SILVER_PILE.copy()
            new["line_template"] = tpl
            new["line_source"] = "inferred"
        print(f"  + {pid} {new['label']}·{new['hero']}  对角={new['diag_reward']['name']}")

    for p in periods:
        p["current"] = False
    periods[-1]["current"] = True

    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        shown = DATA.relative_to(ROOT)
    except ValueError:
        shown = DATA
    print(f"\n已写入 {shown}：{len(periods)} 期，当期 {periods[-1]['id']} {periods[-1]['label']}")


if __name__ == "__main__":
    main()
