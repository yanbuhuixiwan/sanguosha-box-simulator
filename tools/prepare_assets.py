#!/usr/bin/env python3
"""把抓取到的原始素材整理为项目可直接使用的目录结构。

仓库不附带图片素材（武将原画 277MB、皮肤原画 242MB），需在使用前自行抓取。
完整流程：

    python tools/fetch_sgs_assets.py heroes --all   # 1. 官网武将原画 + 各武将皮肤图
    python tools/fetch_wiki_skins.py                # 2. wiki 皮肤原画（已按正式命名落盘）
    python tools/fetch_sgs_assets.py skins          # 3. 绘影堂高清皮肤原画
    python tools/prepare_assets.py                  # 4. 整理为本脚本所述结构
    python tools/build_media_map.py                 # 5. 重建 frontend/src/assets/media-map.json

本脚本负责第 4 步，做两件事：
  1) image/官网素材/武将/<武将>/<武将>_1.jpg  ->  image/武将图片/<武将>.jpg
     官网详情页第 1 张为该武将原画，第 2 张起是无名皮肤图（名字由 wiki 脚本补齐）。
  2) image/官网素材/皮肤/<皮肤名>＊<武将>.jpg  ->  image/皮肤图片/<武将>_<皮肤名>.jpg
     绘影堂为 1920×1305 高清版；同名文件若已由 wiki 脚本生成，以高清版覆盖。

道具图标（image/道具图片/）已在仓库内提供，无需抓取；其中「天工石」「迷迭珠」
为脚本自绘，可用 tools/make_activity_icons.py 重新生成。

用法：
  python tools/prepare_assets.py            # 整理
  python tools/prepare_assets.py --dry-run  # 只统计，不写文件
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "image", "官网素材")
HERO_RAW = os.path.join(RAW, "武将")
SKIN_RAW = os.path.join(RAW, "皮肤")
HERO_OUT = os.path.join(ROOT, "image", "武将图片")
SKIN_OUT = os.path.join(ROOT, "image", "皮肤图片")

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def is_img(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in IMG_EXT


def load_hero_folders() -> dict[str, str]:
    """folder -> 武将名。抓取清单缺失时退化为「folder 即武将名」。"""
    mapping: dict[str, str] = {}
    path = os.path.join(RAW, "heroes.json")
    if os.path.exists(path):
        try:
            rows = json.load(open(path, encoding="utf-8"))
            for r in rows:
                folder, name = r.get("folder"), r.get("name")
                if folder and name:
                    mapping[folder] = name
        except Exception as exc:  # noqa: BLE001
            print(f"  ! heroes.json 解析失败（改用目录名）：{exc}")
    if not os.path.isdir(HERO_RAW):
        return mapping
    for folder in os.listdir(HERO_RAW):
        if os.path.isdir(os.path.join(HERO_RAW, folder)):
            mapping.setdefault(folder, folder)
    return mapping


def stage_heroes(dry: bool) -> tuple[int, int]:
    """返回 (写入数, 跳过数)。"""
    folders = load_hero_folders()
    done = skip = 0
    for folder, name in sorted(folders.items()):
        src_dir = os.path.join(HERO_RAW, folder)
        if not os.path.isdir(src_dir):
            continue
        # 官网详情页第 1 张为武将原画
        src = None
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            cand = os.path.join(src_dir, f"{folder}_1{ext}")
            if os.path.exists(cand):
                src = cand
                break
        if not src:
            continue
        dst = os.path.join(HERO_OUT, name + os.path.splitext(src)[1])
        if os.path.exists(dst):
            skip += 1
            continue
        if not dry:
            os.makedirs(HERO_OUT, exist_ok=True)
            shutil.copy2(src, dst)
        done += 1
    return done, skip


def stage_skins(dry: bool) -> tuple[int, int, int]:
    """返回 (写入数, 覆盖wiki版数, 跳过数)。"""
    if not os.path.isdir(SKIN_RAW):
        return 0, 0, 0
    done = overwritten = skip = 0
    for fn in sorted(os.listdir(SKIN_RAW)):
        if not is_img(fn) or "＊" not in fn:
            continue
        stem = os.path.splitext(fn)[0]
        skin, _, hero = stem.partition("＊")
        if not skin or not hero:
            continue
        dst = os.path.join(SKIN_OUT, f"{hero}_{skin}{os.path.splitext(fn)[1]}")
        exists = os.path.exists(dst)
        if exists:
            # 绘影堂为高清版，若占位文件明显更小则覆盖
            try:
                if os.path.getsize(dst) >= os.path.getsize(os.path.join(SKIN_RAW, fn)):
                    skip += 1
                    continue
            except OSError:
                skip += 1
                continue
            overwritten += 1
        if not dry:
            os.makedirs(SKIN_OUT, exist_ok=True)
            shutil.copy2(os.path.join(SKIN_RAW, fn), dst)
        done += 1
    return done, overwritten, skip


def count(dirpath: str) -> int:
    if not os.path.isdir(dirpath):
        return 0
    return sum(1 for f in os.listdir(dirpath) if is_img(f))


def main() -> int:
    ap = argparse.ArgumentParser(description="整理抓取到的素材为项目目录结构")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    args = ap.parse_args()
    dry = args.dry_run

    if not os.path.isdir(RAW):
        print("未找到 image/官网素材/，请先执行：")
        print("  python tools/fetch_sgs_assets.py heroes --all")
        print("  python tools/fetch_wiki_skins.py")
        print("  python tools/fetch_sgs_assets.py skins")
        return 2

    print("整理武将原画…")
    h_new, h_skip = stage_heroes(dry)
    print(f"  新增 {h_new} 张，已存在跳过 {h_skip} 张")

    print("整理皮肤原画…")
    s_new, s_over, s_skip = stage_skins(dry)
    print(f"  新增 {s_new} 张（其中覆盖 wiki 版 {s_over} 张），已存在或低清跳过 {s_skip} 张")

    suffix = "（演练模式，未写入）" if dry else ""
    print(f"\n当前素材数量{suffix}：")
    print(f"  image/武将图片/  {count(HERO_OUT)} 张")
    print(f"  image/皮肤图片/  {count(SKIN_OUT)} 张")
    print(f"  image/道具图片/  {count(os.path.join(ROOT, 'image', '道具图片'))} 张")

    if not dry:
        print("\n下一步：python tools/build_media_map.py")
        print("        cd frontend && npm run build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
