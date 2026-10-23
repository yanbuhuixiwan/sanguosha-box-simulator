"""把旧版 22 期（corr-01 ~ corr-22）的回廊进度迁移到重建后的 77 期 id。

重建后 id 按日期重新编号，旧记录会“失联”。这里按 (皮肤名, 武将) 一一对应，
把 corridor_state.period 指向新 id；新旧同时存在的用户则合并（取较大抽数、碎片并集）。

    python tools/migrate_corridor_state.py --dry-run
    python tools/migrate_corridor_state.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "sanguosha.db"
CORRIDOR = ROOT / "backend" / "app" / "data" / "corridor.json"

# 旧版 corr-01 ~ corr-22 的期名 / 武将（重建前的数据）
OLD = [
    ("才广志宏", "周不疑"), ("长沙阻敌", "星黄忠"), ("四方归心", "神曹操"),
    ("沙场蛮花", "花鬘"), ("龙兴蜀川", "刘焉"), ("能工巧匠", "马钧"),
    ("枭龙破渊", "曹髦"), ("荡然由心", "鲁肃"), ("谋乱长安", "贾诩"),
    ("力引三矢", "沙摩柯"), ("盟固策合", "鲁肃"), ("深情故剑", "鲍三娘"),
    ("五虎后承", "廖化"), ("刹那绽华", "戏志才"), ("醉里看剑", "友徐庶"),
    ("心宇同一", "孙寒华"), ("操刀必割", "徐盛"), ("万魔荡除", "神太史慈"),
    ("怀曦赴煌", "神荀彧"), ("国泰民丰", "势国渊"), ("风霆啸野", "神马超"),
    ("烬策焚粮", "许攸"),
]


def main() -> None:
    dry = "--dry-run" in sys.argv
    periods = json.loads(CORRIDOR.read_text(encoding="utf-8"))["periods"]
    by_key: dict[tuple[str, str], list[dict]] = {}
    for p in periods:
        by_key.setdefault((p["skin"], p["hero"]), []).append(p)

    mapping: dict[str, str] = {}
    for num, (skin, hero) in enumerate(OLD, start=1):
        old_id = f"corr-{num:02d}"
        cands = by_key.get((skin, hero))
        if not cands:
            continue
        # 同名多期取最接近的一期（这里取最新一期，返场即最新）
        new_id = sorted(cands, key=lambda p: p["dates"])[-1]["id"]
        if new_id != old_id:
            mapping[old_id] = new_id

    print(f"可映射旧期数: {len(mapping)} / {len(OLD)}")
    for k, v in mapping.items():
        print(f"  {k} -> {v}")

    if not mapping:
        return

    db = sqlite3.connect(DB)
    cur = db.cursor()
    moved = merged = skipped = 0
    for old_id, new_id in mapping.items():
        cur.execute("SELECT user_id, fragments, lines, pulls, finished FROM corridor_state WHERE period=?", (old_id,))
        olds = cur.fetchall()
        for uid, frags, lines, pulls, finished in olds:
            cur.execute("SELECT fragments, lines, pulls, finished FROM corridor_state WHERE user_id=? AND period=?", (uid, new_id))
            exist = cur.fetchone()
            if exist:
                f2, l2, p2, fin2 = exist
                frag = sorted(set(json.loads(frags or "[]")) | set(json.loads(f2 or "[]")))
                ln = sorted(set(json.loads(lines or "[]")) | set(json.loads(l2 or "[]")))
                if dry:
                    merged += 1
                    continue
                cur.execute(
                    "UPDATE corridor_state SET fragments=?, lines=?, pulls=?, finished=? WHERE user_id=? AND period=?",
                    (json.dumps(frag), json.dumps(ln), max(pulls or 0, p2 or 0), max(finished or 0, fin2 or 0), uid, new_id),
                )
                cur.execute("DELETE FROM corridor_state WHERE user_id=? AND period=?", (uid, old_id))
                merged += 1
            else:
                if dry:
                    moved += 1
                    continue
                cur.execute("UPDATE corridor_state SET period=? WHERE user_id=? AND period=?", (new_id, uid, old_id))
                moved += 1
        # 无人认领的旧记录直接丢弃
        cur.execute("SELECT COUNT(*) FROM corridor_state WHERE period=?", (old_id,))
        skipped += cur.fetchone()[0]

    if dry:
        print(f"[dry-run] 迁移 {moved} 条，合并 {merged} 条")
        db.close()
        return
    db.commit()
    db.close()
    print(f"已迁移 {moved} 条，合并 {merged} 条")
    if skipped:
        print(f"丢弃无法对应的旧记录 {skipped} 条（期名在官网清单中不存在）")


if __name__ == "__main__":
    main()
