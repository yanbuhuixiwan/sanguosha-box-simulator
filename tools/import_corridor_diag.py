"""批量导入每期梦之回廊的「对角奖励皮肤」。

数据源：小程序「三国杀移动版盒子模拟器」里查到的往期对角皮肤。
两种用法（可混用）：

  1) 填表：编辑 data/corridor_diag.xlsx（推荐，Excel/WPS 直接开）
         表头是 `期号,期数,期名,开始日期,本期大奖皮肤,对角皮肤（请填这里）,当前推定值（仅参考）`，
         只需在「对角皮肤（请填这里）」那一列填，例如 `风霆啸野·神马超`；没填的行会被跳过。
         列顺序可以随便调（脚本按列名找「期号」「对角」）。
         也认 `data/corridor_diag.csv`（同样表头），两个文件都在时读**修改时间较新**的那个。

  2) 命令行一次给几期：
         python tools/import_corridor_diag.py corr-77=风霆啸野·神马超 corr-76=怀曦赴煌·神荀彧

皮肤名支持 `·` 和官方公告里的 `*` 两种写法，脚本统一成 `·`。
校验：期号必须存在于 corridor.json；皮肤名会去 media-map 里查有没有对应原画
（`<武将>_<皮肤名>.jpg`），查不到只警告、照样写入，但阵盘会显示占位格。
脚本幂等，重复导入结果一致；改完记得重启后端（JSON 有缓存）。
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend/app/data/corridor.json"
MEDIA = ROOT / "frontend/src/assets/media-map.json"
CSV_PATH = ROOT / "data/corridor_diag.csv"
XLSX_PATH = ROOT / "data/corridor_diag.xlsx"


def norm(name: str) -> str:
    """统一皮肤写法：去掉空白，`*` → `·`。"""
    return (name or "").strip().replace("*", "·").replace("・", "·")


def parse_entry(period: str, skin: str, periods: dict, skins: dict) -> tuple[dict | None, list[str]]:
    warns: list[str] = []
    period = period.strip()
    name = norm(skin)
    if not period or not name:
        return None, ["空行/空值"]
    if period not in periods:
        return None, [f"{period} 不是有效的期号"]
    if "·" not in name:
        return None, [f"{period} 的皮肤名 `{name}` 缺少「·武将」后缀"]
    skin_part, hero_part = name.split("·", 1)
    if f"{hero_part}_{skin_part}" not in skins:
        warns.append(f"{period} 素材里没有原画 `{hero_part}_{skin_part}.jpg`（会显示占位格）")
    reward = {
        "key": f"skin:{name}",
        "name": name,
        "kind": "skin",
        "rarity": periods[period].get("final_prize", {}).get("rarity", "legendary"),
        "qty": 1,
    }
    return reward, warns


def read_cells() -> list[list[str]]:
    """读表格（xlsx 优先，两个都在时取修改时间较新的那个）。"""
    files = [p for p in (CSV_PATH, XLSX_PATH) if p.exists()]
    if not files:
        return []
    src = max(files, key=lambda p: p.stat().st_mtime)
    if src.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError:
            print("  ! 没装 openpyxl，改读 CSV")
            return read_cells() if src is not CSV_PATH and CSV_PATH.exists() else []
        ws = load_workbook(src, data_only=True).active
        return [["" if v is None else str(v).strip() for v in row] for row in ws.iter_rows(values_only=True)]
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        return [[c.strip() for c in row] for row in csv.reader(f)]


def collect_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for arg in sys.argv[1:]:
        if "=" in arg:
            p, s = arg.split("=", 1)
            pairs.append((p, s))

    rows = read_cells()
    pi = si = None
    for row in rows:
        if not row or row[0].lstrip().startswith("#"):
            continue
        cells = [c.strip() for c in row]
        if pi is None:
            # 表头行：按列名定位「期号」「对角」，列顺序可以随便调
            has_period = any("期号" in c or c.lower() == "period" for c in cells)
            has_diag = any("对角" in c for c in cells)
            if has_period and has_diag:
                pi = next(i for i, c in enumerate(cells) if "期号" in c or c.lower() == "period")
                si = next(i for i, c in enumerate(cells) if "对角" in c)
                continue
            pi, si = 0, 1  # 没有表头：约定「期号, 皮肤」
        if len(cells) <= max(pi, si):
            continue
        period, skin = cells[pi], cells[si]
        if not period or not skin:
            continue  # 还没填的行，静默跳过
        pairs.append((period, skin))
    return pairs


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    periods = {p["id"]: p for p in data["periods"]}
    skins = json.loads(MEDIA.read_text(encoding="utf-8"))["skins"] if MEDIA.exists() else {}

    pairs = collect_pairs()
    if not pairs:
        print("没有可导入的数据。请在 data/corridor_diag.xlsx 的「对角皮肤（请填这里）」列填，或用命令行 corr-77=皮肤名·武将")
        return

    changed = 0
    for period, skin in pairs:
        reward, warns = parse_entry(period, skin, periods, skins)
        for w in warns:
            print("  ! " + w)
        if not reward:
            continue
        p = periods[period]
        old = (p.get("diag_reward") or {}).get("name", "（空）")
        if old == reward["name"]:
            print(f"  = {period} 已是 {reward['name']}，跳过")
            continue
        p["diag_reward"] = reward
        changed += 1
        print(f"  ✓ {period}  {old} → {reward['name']}")

    if changed:
        DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n已更新 {changed} 期，写入 {DATA.relative_to(ROOT)}。记得重启后端让缓存失效。")
    else:
        print("\n没有需要改动的期次。")


if __name__ == "__main__":
    main()
