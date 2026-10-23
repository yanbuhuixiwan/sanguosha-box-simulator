"""按官网《梦之回廊—XX 概率公示》重建 corridor.json。

数据来源
--------
· 官网公告列表 /pc/news-list-1004.html 里全部「【梦之回廊—XX】概率公示」（共 77 期，
  2023-11-24 ~ 2026-10-16），原始清单见 tools/corridor_official.json；
· 每期的「碎片奖励」道具池与「产出新碎片概率」表，直接转录官网公示图：
    - 碎片奖励（各期一致）：
        菜篮子*2 9.495% / 欢乐豆*50 5% / 点将卡*2 15% / 换将卡*2 20% / 手气卡*2 20%
        进阶丹*1 10% / 雁翎甲*1 10% / 招募令*1 6% / 史诗宝珠碎片*1 4%
        史诗宝珠*1 0.5% / 史诗宝珠*66 0.005%
    - 新碎片概率：前 20 个各期相同，第 21~25 个按期分七档（见 RATE_TABLES）；
· 保底抽数按期不同：终端档 0.29% → 600 抽、0.41% → 500 抽、1.03/1.15% → 250 抽，
  三倍概率期（末档 8%）→ 150 抽。pity_limit 即按该期概率表推导出的保底抽数。

用法
----
    python tools/build_corridor.py            # 写入 corridor.json
    python tools/build_corridor.py --report   # 只打印各档统计，不写文件
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend" / "app" / "data" / "corridor.json"
OFFICIAL = ROOT / "tools" / "corridor_official.json"

# 前 20 个碎片的产出概率，各期完全一致（官网公示）
HEAD_RATES = [
    100.0, 96.0, 92.0, 88.0, 84.0,
    80.0, 76.0, 72.0, 68.0, 64.0,
    42.86, 40.0, 37.14, 34.29, 31.43,
    25.0, 22.5, 20.0, 17.5, 15.0,
]

# 第 21~25 个碎片：官网公示图里共出现 7 种不同的概率表
RATE_TABLES = {
    # 末档 1.03%：最标准的 25 行表（42 期）
    "A": [7.62, 6.10, 4.57, 3.05, 1.03],
    # 三倍概率期：末档 8%（落纸如飞 / 幻蝶萦魂 / 点墨惊龙）
    "B": [24.0, 20.0, 16.0, 12.0, 8.0],
    # 末档 0.29%：最难的一档（心宇同一等 9 期）
    "C": [2.44, 1.95, 1.46, 0.98, 0.29],
    # 末档 0.41%：枭龙破渊（500 抽档）
    "D": [6.98, 5.58, 4.19, 0.93, 0.41],
    # 末档 1.84%
    "E": [10.11, 8.04, 5.98, 3.91, 1.84],
    # 末档 4%
    "F": [20.0, 16.0, 12.0, 8.0, 4.0],
    # 末档 1.15%
    "G": [7.62, 6.00, 4.38, 2.77, 1.15],
}

# 每档对应的保底抽数（按概率表推导：sum(1/p) 取整，再对齐官方/社区口径）
#   A/G ≈ 230 抽 → 250；C ≈ 660 抽 → 600（官方口径）；D ≈ 460 抽 → 500；
#   E ≈ 171 抽 → 180；F ≈ 109 抽 → 120；B ≈ 88 抽 → 150（官方「最黑 150」）
PITY = {"A": 250, "B": 150, "C": 600, "D": 500, "E": 180, "F": 120, "G": 250}

# 碎片奖励（官网公示「碎片奖励」表，各期一致）
DRAW_POOL = [
    ("basket", "菜篮子", 2, 9495, "common", "basket"),
    ("bean", "欢乐豆", 50, 5000, "common", "bean"),
    ("pick_card_2", "点将卡", 2, 15000, "common", "pick"),
    ("swap_card_2", "换将卡", 2, 20000, "common", "swap"),
    ("luck_card_2", "手气卡", 2, 20000, "common", "luck"),
    ("pill_1", "进阶丹", 1, 10000, "rare", "pill"),
    ("armor_1", "雁翎甲", 1, 10000, "rare", "armor"),
    ("token_1", "招募令", 1, 6000, "rare", "token"),
    ("orb_shard_1", "史诗宝珠碎片", 1, 4000, "epic", "shard"),
    ("orb_1", "史诗宝珠", 1, 500, "legendary", "orb"),
    ("orb_66", "史诗宝珠", 66, 5, "legendary", "orb"),
]


def hero_skin_key(skin: str, hero: str) -> str:
    return f"skin:{skin}·{hero}"


def build_periods(official: list[dict]) -> list[dict]:
    periods = []
    for idx, row in enumerate(official, start=1):
        table = row["table"]
        rates = HEAD_RATES + RATE_TABLES[table]
        assert len(rates) == 25, row
        periods.append(
            {
                "id": f"corr-{idx:02d}",
                "label": row["name"],
                "skin": row["name"],
                "hero": row["hero"],
                "dates": row["date"],
                "table": table,
                "fragment_rates": rates,
                "pity_limit": PITY[table],
                "final_prize": {
                    "key": hero_skin_key(row["name"], row["hero"]),
                    "name": f"{row['name']}·{row['hero']}",
                    "kind": "skin",
                    "rarity": "legendary",
                    "qty": 1,
                },
                "current": False,
            }
        )
    periods.sort(key=lambda p: p["dates"])  # 早 → 晚
    for idx, p in enumerate(periods, start=1):
        p["id"] = f"corr-{idx:02d}"
    periods[-1]["current"] = True
    return periods


def main() -> None:
    report = "--report" in __import__("sys").argv
    base = json.loads(DATA.read_text(encoding="utf-8"))
    official = json.loads(OFFICIAL.read_text(encoding="utf-8"))

    periods = build_periods(official)
    current = periods[-1]

    pool = [
        {
            "key": key,
            "name": name,
            "qty": qty,
            "weight": weight,
            "kind": "item",
            "rarity": rarity,
            "icon": icon,
        }
        for key, name, qty, weight, rarity, icon in DRAW_POOL
    ]
    total = sum(e["weight"] for e in pool)
    assert total == 100000, total

    # 共享字段（期数据会覆盖 fragment_rates / pity_limit）
    base["draw_pool"] = pool
    base["fragment_rates"] = current["fragment_rates"]
    base["pity_limit"] = current["pity_limit"]
    base["fragment_rate_note"] = (
        "官方公示：第 1~5 个碎片 84.00%~100.00%，第 6~10 个 64.00%~80.00%，"
        "第 11~15 个 31.43%~42.86%，第 16~20 个 15.00%~25.00%，"
        "第 21~25 个按期不同（末期最低 0.29%，保底 600 抽）。"
    )
    base["rules"] = [
        "迷迭珠 300 元宝 / 颗，可在本页直接购买。",
        "回忆 1 次或 10 次，单次概率与随机方式完全相同。",
        "每次回忆获得 1 份随机奖励 + 1 个记忆碎片，碎片不会超出阵盘 25 种。",
        "碎片可以重复点亮；累计碎片数越多，开出新碎片的概率越低。",
        "阵盘 5×5，横 5 条、竖 5 条、斜 2 条，共 12 条连线，每条线的奖励只能领一次。",
        "集齐 25 种碎片，领取本期终极大奖（传说动态皮肤）。",
        "每期保底抽数不同：250 / 500 / 600 抽等，累计抽满保底抽数必定集齐并领取终极大奖。",
    ]
    base["final_prize"] = current["final_prize"]
    base["period"] = f"本期 · {current['label']}·{current['hero']}"
    base["theme"] = current["label"]
    base["periods"] = periods

    dist = Counter(p["table"] for p in periods)
    print(f"期数: {len(periods)}  年份: {dict(Counter(p['dates'][:4] for p in periods))}")
    print("档位分布:", dict(dist))
    print("保底分布:", dict(Counter(p["pity_limit"] for p in periods)))
    print("当前期:", current["id"], current["label"], current["hero"], current["pity_limit"])

    if report:
        return
    DATA.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已写入", DATA)


if __name__ == "__main__":
    main()
