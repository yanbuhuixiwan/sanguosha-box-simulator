"""给 77 期梦之回廊逐期补齐对角奖励（**每期只有一个皮肤**）。

背景：corridor.json 顶层的 12 条 lines 是各期共用的模板，斜线奖励因此被写死成
「针砭去疾·华佗 / 国之柱石·诸葛亮」，77 期全都一样。官方每期对角给的是**往期复刻皮肤**，
且对角只放**一个**皮肤（主/副两条斜线共用这一个奖励），所以这里按规则逐期生成：

    对角皮肤 = 该期往前 2 期的大奖皮肤
    往前不够（前 2 期）就改用往后同样的间隔，避免复刻到「未来」的皮肤

结果写进每期的 `diag_reward` 字段（单个对象），可手工改成官方实际值；后端
gacha.corridor_episode 读这个字段，同时覆盖 lines 里 diag-1 / diag-2 的 reward。
脚本幂等，重复运行结果一致。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend/app/data/corridor.json"


def pick_index(idx: int, back: int, total: int) -> int:
    j = idx - back
    if j < 0:  # 这个方向没有往期，改取往后同样的间隔
        j = idx + back
    if j >= total:
        j %= total
    return j


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    periods = data["periods"]
    total = len(periods)

    for idx, p in enumerate(periods):
        skin = dict(periods[pick_index(idx, 2, total)]["final_prize"])
        skin["qty"] = 1
        p["diag_reward"] = skin
        p.pop("diag_rewards", None)  # 旧的 [主, 副] 两皮肤字段，已废弃

    # 顶层模板也统一成单皮肤，避免缺字段时又冒出两个不同皮肤
    fallback = dict(periods[0]["diag_reward"])
    for line in data["lines"]:
        if line["id"].startswith("diag-"):
            line["reward"] = dict(fallback)

    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for i in (0, 1, 4, 68, 74, 76):
        p = periods[i]
        print(f"{p['id']} 本期 {p['skin']}·{p['hero']}  ->  对角 {p['diag_reward']['name']}")
    print(f"\n共写入 {total} 期 diag_reward（每期 1 个皮肤）")


if __name__ == "__main__":
    main()
