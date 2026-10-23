"""把 2024–2026 官方上线过的「所有」限时礼盒（含已下架/删除）补进 boxes.json。

数据来源：三国杀移动版官网《道具概率公示集中贴》
https://www.sanguosha.cn/index.php/pc/news-detail-602.html
各期大奖武将来自官网对应期活动公告（如 news-detail-2119 寒柏凌霜、2343 剑心如玉等）。

核心规律（据官方「盒子概率一览表」及既有数据验证）：
  每一期盒子奖励不同但权重相同——总权重 20000，公共道具与尾部大奖结构固定，
  仅「精品武将 / 皮肤动态包 / 权3 / 权1」四格按当期主推武将替换。

用法：
    python tools/build_all_boxes.py            # 增量合入（不改既有 23 只）
    python tools/build_all_boxes.py --report   # 只打印将新增的盒子，不写文件
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pypinyin import lazy_pinyin

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend" / "app" / "data" / "boxes.json"

SOURCE = "三国杀移动版《道具概率公示集中贴》 https://www.sanguosha.cn/index.php/pc/news-detail-602.html"

# ---------------------------------------------------------------- 通用权重模板
# 公共道具（每期相同），权重照抄官方「盒子概率一览表」
# 200 元宝正常盒：总权重 20000
COMMON_ITEMS = [
    ("史诗体验卡", 1, 1000, "exp_card_1", "common", "exp"),
    ("欢乐豆", 50, 1000, "bean", "common", "bean"),
    ("菜篮子", 2, 1360, "basket", "common", "basket"),
    ("换将卡", 2, 6500, "swap_card_2", "common", "swap"),
    ("手气卡", 2, 6500, "luck_card_2", "common", "luck"),
    ("进阶丹", 2, 1000, "pill_1", "rare", "pill"),
    ("雁翎甲", 1, 1000, "armor_1", "rare", "armor"),
    ("招募令", 1, 1000, "token_1", "rare", "token"),
    ("史诗宝珠碎片", 1, 200, "orb_shard_1", "rare", "shard"),
    ("菜篮子", 99, 200, "basket", "rare", "basket"),
]
# 100 元宝半价盒：总权重 10000（参照 anniversary_2026 半价盒的公共权重）
COMMON_ITEMS_HALF = [
    ("史诗体验卡", 1, 500, "exp_card_1", "common", "exp"),
    ("欢乐豆", 22, 500, "bean", "common", "bean"),
    ("菜篮子", 2, 680, "basket", "common", "basket"),
    ("换将卡", 2, 3250, "swap_card_2", "common", "swap"),
    ("手气卡", 2, 3250, "luck_card_2", "common", "luck"),
    ("进阶丹", 1, 500, "pill_1", "rare", "pill"),
    ("雁翎甲", 1, 500, "armor_1", "rare", "armor"),
    ("招募令", 1, 500, "token_1", "rare", "token"),
    ("史诗宝珠碎片", 1, 100, "orb_shard_1", "rare", "shard"),
    ("菜篮子", 99, 100, "basket", "rare", "basket"),
]
# 尾部大奖（每期替换 good / skin / weight3 / weight1 四格）
# 固定：精品武将(100) 史诗宝珠*1(100) 将魂*1000(15) 皮肤动态包(15) 权3(3) 宝珠66(1) 权1(1)

# ---------------------------------------------------------------- 品级规范
HERO_QUALITY = {
    "SP甄姬": "epic", "傅佥": "epic", "势周瑜": "epic", "势国渊": "epic",
    "势小乔": "epic", "势曹真": "good", "势田丰": "good", "势董昭": "epic",
    "势邓艾": "epic", "势钟会": "epic", "势陈祗": "good", "友庞统": "good",
    "友诸葛亮": "epic", "周群": "epic", "孙翊": "good", "崔芙": "epic",
    "张奋": "epic", "彭羕": "good", "曹髦": "epic", "灵雎": "epic",
    "王凌": "epic", "王濬": "good", "王粲": "epic", "界严颜": "good",
    "界于禁": "epic", "界刘备": "good", "界刘表": "good", "界孙鲁班": "good",
    "界张嶷": "good", "界曹植": "good", "界曹真": "epic", "界朱治": "good",
    "界朱然": "epic", "界沮授": "epic", "界韩当": "good", "神华佗": "epic",
    "神司马懿": "epic", "神姜维": "epic", "神荀彧": "epic", "神鲁肃": "epic",
    "神甘宁": "epic", "神刘备": "epic", "管融": "epic", "胡班": "good",
    "花鬘": "epic", "董允": "epic", "蒋济": "epic", "谋公孙瓒": "epic",
    "谋关羽": "epic", "谋卢植": "good", "谋夏侯惇": "epic", "谋张郃": "good",
    "谋曹丕": "epic", "谋朱然": "epic", "谋诸葛亮": "epic", "谋韩当": "good",
    "谋高顺": "good", "谋孙权": "epic", "谋孙尚香": "epic", "谋刘备": "epic",
    "谋吕布": "epic", "谯周": "epic", "贾充": "good", "郝昭": "epic",
    "阮慧": "good", "马云騄": "epic", "骥张辽": "epic", "骥李典": "good",
    "势于吉": "epic", "势太史慈": "epic", "势陆郁生": "epic", "势桓阶": "epic",
    "孙寒华": "epic", "十常侍": "epic", "羊徽瑜": "epic", "鲍三娘": "epic",
    "孙邵": "good",
}


def py(text: str) -> str:
    clean = re.sub(r"[·\s&]", "", text)
    return "".join(lazy_pinyin(clean)).replace("·", "").lower()


def norm_hero(name: str) -> str:
    return re.sub(r"(?<=[势谋界神友骥])·", "", name)


def hero_entry(name: str, weight: int) -> dict:
    n = norm_hero(name)
    return {
        "key": f"hero_{py(n)}", "name": n, "qty": 1, "weight": weight,
        "kind": "hero", "rarity": HERO_QUALITY.get(n, "epic"), "icon": "hero",
    }


def skin_entry(name: str, weight: int) -> dict:
    """「明良千古·刘备动态包」-> skin key。"""
    n = name.replace("*", "·").replace("＊", "·")
    a, _, b = n.partition("·")
    hero = b.replace("动态包", "") if b else a
    return {
        "key": f"skin_{py(hero)}", "name": n, "qty": 1, "weight": weight,
        "kind": "skin", "rarity": "epic", "icon": "skin",
    }


def build_pool(good: str, skin: str | None, w3: str, w1: str, half: bool = False) -> list[dict]:
    """按通用模板 + 四格大奖组装卡池；half=True 用半价盒权重（总 10000）。"""
    template = COMMON_ITEMS_HALF if half else COMMON_ITEMS
    pool = []
    for name, qty, w, key, rarity, icon in template:
        pool.append({
            "key": key, "name": name, "qty": qty, "weight": w,
            "kind": "item", "rarity": rarity, "icon": icon,
        })
    pool.append(hero_entry(good, 50 if half else 100))     # 精品武将
    pool.append({"key": "orb_1", "name": "史诗宝珠", "qty": 1,
                 "weight": 50 if half else 100,
                 "kind": "item", "rarity": "epic", "icon": "orb"})
    pool.append({"key": "soul_1000", "name": "将魂", "qty": 1000,
                 "weight": 8 if half else 15,
                 "kind": "item", "rarity": "epic", "icon": "soul"})
    if skin:
        pool.append(skin_entry(skin, 8 if half else 15))
    pool.append(hero_entry(w3, 2 if half else 3))           # 权3
    if half:
        pool.append({"key": "orb_33", "name": "史诗宝珠", "qty": 33, "weight": 1,
                     "kind": "item", "rarity": "epic", "icon": "orb"})
    else:
        pool.append({"key": "orb_66", "name": "史诗宝珠", "qty": 66, "weight": 1,
                     "kind": "item", "rarity": "epic", "icon": "orb"})
    pool.append(hero_entry(w1, 1))                          # 权1
    total = sum(e["weight"] for e in pool)
    for e in pool:
        e["probability"] = round(e["weight"] / total * 100, 4)
    return pool


def box(id, name, year, season, released, price, theme, desc, good, skin, w3, w1):
    half = price == 100
    pool = build_pool(good, skin, w3, w1, half=half)
    return {
        "id": id, "name": name,
        "subtitle": f"往期礼盒 · {season}限定",
        "category": "half" if half else "normal",
        "category_name": "半价盒子" if half else "正常盒子",
        "price": price,
        "total_weight": sum(e["weight"] for e in pool),
        "theme": theme, "year": year, "kind": "past",
        "released": released, "source": SOURCE, "description": desc,
        "bonus": (
            [{"key": "feather", "name": "雁翎", "kind": "item", "rarity": "rare", "qty": 10},
             {"key": "soul_1000", "name": "将魂", "kind": "item", "rarity": "epic", "qty": 1}]
            if half else
            [{"key": "feather", "name": "雁翎", "kind": "item", "rarity": "rare", "qty": 20},
             {"key": "soul_1000", "name": "将魂", "kind": "item", "rarity": "epic", "qty": 2}]
        ),
        "pool": pool,
    }


# ---------------------------------------------------------------- 缺失盒子清单
# (id, 名称, 年, 季节, 上线日, 价格, 主题, 描述, 精品武将, 皮肤, 权3, 权1)
NEW_BOXES = [
    # ============================================================ 2026
    box("qianhuan_2026", "2026年千幻万劫", 2026, "千幻万劫", "2026-10-01", 200, "crimson",
        "千幻万劫，万象更新。200 元宝一抽，势于吉、神甘宁同候有缘人。",
        "孙邵", "明良千古·刘备动态包", "势于吉", "神甘宁"),
    box("chuqiu_2026", "2026年初秋礼盒", 2026, "初秋", "2026-09-12", 200, "gold",
        "秋高气爽，礼盒纳福。200 元宝一抽，神荀彧等大奖静候有缘人。",
        "孙邵", None, "神荀彧", "神甘宁"),
    box("rence_2026", "2026年仁策无双", 2026, "仁策无双", "2026-08-29", 200, "plum",
        "仁策无双，谋定天下。200 元宝一抽，谋刘备、神刘备同候有缘人。",
        "孙邵", "明良千古·刘备动态包", "神刘备", "谋刘备"),
    box("liejian_2026", "2026年烈箭红妆", 2026, "烈箭红妆", "2026-08-29", 200, "crimson",
        "烈箭红妆，巾帼不让。200 元宝一抽，势太史慈、鲍三娘同候有缘人。",
        "孙邵", None, "鲍三娘", "势太史慈"),
    box("zhongyuan_2026", "2026年中元礼盒", 2026, "中元", "2026-08-22", 200, "amber",
        "中元月夜，故人入匣。200 元宝一抽，十常侍、羊徽瑜同候有缘人。",
        "孙邵", None, "羊徽瑜", "十常侍"),
    box("qixi_2026", "2026年七夕礼盒", 2026, "七夕", "2026-08-15", 200, "plum",
        "七夕鹊桥，佳偶天成。200 元宝一抽，神甘宁等大奖静候有缘人。",
        "孙邵", None, "鲍三娘", "神甘宁"),
    box("yongguan_2026", "2026年勇冠三军", 2026, "勇冠三军", "2026-08-01", 200, "crimson",
        "勇冠三军，所向披靡。200 元宝一抽，谋吕布、灵雎同候有缘人。",
        "孙邵", None, "灵雎", "谋吕布"),
    box("jianxin_2026", "2026年剑心如玉", 2026, "剑心如玉", "2026-07-04", 100, "azure",
        "剑心如玉，温润而泽。100 元宝一抽，孙寒华等大奖静候有缘人。",
        "孙邵", None, "孙寒华", "神甘宁"),
    box("qianlong_2026", "2026年潜龙在渊", 2026, "潜龙在渊", "2026-07-04", 100, "azure",
        "潜龙在渊，一飞冲天。100 元宝一抽，曹髦等大奖静候有缘人。",
        "孙邵", None, "曹髦", "神甘宁"),
    box("liexin_2026", "2026年烈心柔情", 2026, "烈心柔情", "2026-06-19", 200, "plum",
        "烈心柔情，巾帼英豪。200 元宝一抽，谋孙尚香、鲍三娘同候有缘人。",
        "孙邵", None, "鲍三娘", "谋孙尚香"),
    box("moudingjiangdong_2026", "2026年谋定江东", 2026, "谋定江东", "2026-06-19", 200, "crimson",
        "谋定江东，运筹帷幄。200 元宝一抽，谋孙权、神甘宁同候有缘人。",
        "孙邵", None, "神甘宁", "谋孙权"),
    box("mangzhong_2026", "2026年芒种礼盒", 2026, "芒种", "2026-05-30", 200, "gold",
        "芒种忙种，将星在望。200 元宝一抽，谋关羽、神鲁肃同候有缘人。",
        "孙邵", None, "神鲁肃", "谋关羽"),
    box("xiaoman_2026", "2026年小满礼盒", 2026, "小满", "2026-05-16", 200, "azure",
        "小满未满，将心未老。200 元宝一抽，神孙策等大奖静候有缘人。",
        "孙邵", None, "神孙策", "神甘宁"),
    box("huguo_2026", "2026年护国佑民", 2026, "护国佑民", "2026-05-01", 200, "crimson",
        "护国佑民，忠义无双。200 元宝一抽，神马超等大奖静候有缘人。",
        "孙邵", None, "神马超", "神甘宁"),
    box("chunfeng_2026", "2026年春风礼盒", 2026, "春风", "2026-04-04", 200, "azure",
        "春风得意，礼盒纳祥。200 元宝一抽，神姜维等大奖静候有缘人。",
        "孙邵", None, "谋张郃", "神姜维"),
    box("moudingtianxia_2026", "2026年谋定天下", 2026, "谋定天下", "2026-03-07", 200, "crimson",
        "谋定天下，步步为营。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "骥张辽", "谋关羽"),
    box("jinma_2026", "2026年金马贺岁", 2026, "金马贺岁", "2026-02-15", 200, "gold",
        "金马贺岁，马到成功。200 元宝一抽，神姜维等大奖静候有缘人。",
        "孙邵", None, "谋曹丕", "神姜维"),
    box("suimo_2026", "2026年岁末礼盒", 2026, "岁末", "2026-01-24", 200, "crimson",
        "岁末辞旧，礼盒迎新。200 元宝一抽，友诸葛亮等大奖静候有缘人。",
        "孙邵", None, "势邓艾", "友诸葛亮"),
    box("fuyun_2026", "2026年福运连连", 2026, "福运连连", "2026-01-10", 200, "crimson",
        "福运连连，好运连连。200 元宝一抽，神甘宁、谋曹丕同候有缘人。",
        "孙邵", None, "谋曹丕", "神甘宁"),
    box("weizhen_2026", "2026年威震四方", 2026, "威震四方", "2026-01-01", 200, "crimson",
        "威震四方，名动天下。200 元宝一抽，友诸葛亮等大奖静候有缘人。",
        "孙邵", None, "势钟会", "友诸葛亮"),
    # ============================================================ 2025
    box("dongzhi_2025", "2025年冬至礼盒", 2025, "冬至", "2025-12-20", 200, "azure",
        "冬至阳生，岁回律转。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "崔芙", "谋关羽"),
    box("zhiyuan_2025", "2025年智渊凤仪", 2025, "智渊凤仪", "2025-11-22", 200, "plum",
        "智渊凤仪，德才兼备。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "董允", "谋关羽"),
    box("kuanghuan_2025", "2025年狂欢礼盒", 2025, "狂欢", "2025-11-08", 200, "crimson",
        "狂欢盛宴，礼盒助兴。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "蒋济", "谋关羽"),
    box("shuangjiang_2025", "2025年霜降礼盒", 2025, "霜降", "2025-10-18", 200, "gold",
        "霜降叶落，礼盒纳福。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "势国渊", "谋关羽"),
    box("fujun_2025", "2025年辅君谋远", 2025, "辅君谋远", "2025-10-01", 200, "crimson",
        "辅君谋远，忠言逆耳。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "界刘备", "谋关羽"),
    box("qiuri_2025", "2025年秋日礼盒", 2025, "秋日", "2025-09-12", 200, "gold",
        "秋日胜春朝，礼盒纳祥。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "势国渊", "谋关羽"),
    box("dazhan_2025", "2025年大展宏图", 2025, "大展宏图", "2025-08-30", 200, "crimson",
        "大展宏图，鹏程万里。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "管融", "谋关羽"),
    box("jiandan_2025", "2025年剑胆琴心", 2025, "剑胆琴心", "2025-08-15", 200, "azure",
        "剑胆琴心，侠骨柔情。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "势田丰", "谋关羽"),
    box("hanbai_2025", "2025年寒柏凌霜", 2025, "寒柏凌霜", "2025-08-02", 200, "azure",
        "寒柏凌霜，傲雪凌霜。200 元宝一抽，势陆郁生等大奖静候有缘人。",
        "孙邵", None, "势陆郁生", "神甘宁"),
    box("qimeng_2025", "2025年绮梦碎影", 2025, "绮梦碎影", "2025-08-02", 200, "plum",
        "绮梦碎影，如梦似幻。200 元宝一抽，清河公主等大奖静候有缘人。",
        "孙邵", None, "清河公主", "神甘宁"),
    box("xianfeng_2025", "2025年仙风逸韵", 2025, "仙风逸韵", "2025-07-12", 200, "azure",
        "仙风逸韵，超凡脱俗。200 元宝一抽，神甘宁等大奖静候有缘人。",
        "孙邵", None, "神甘宁", "谋曹丕"),
    box("qingguo_2025", "2025年倾国倾城", 2025, "倾国倾城", "2025-07-12", 200, "plum",
        "倾国倾城，一笑倾城。200 元宝一抽，灵雎等大奖静候有缘人。",
        "孙邵", None, "灵雎", "谋曹丕"),
    box("chidan_2025", "2025年赤胆霜谋", 2025, "赤胆霜谋", "2025-06-28", 200, "crimson",
        "赤胆霜谋，忠勇双全。200 元宝一抽，谋曹丕等大奖静候有缘人。",
        "孙邵", None, "谋曹丕", "神甘宁"),
    box("duqi_2025", "2025年独骑破军", 2025, "独骑破军", "2025-06-14", 200, "azure",
        "独骑破军，万夫莫当。200 元宝一抽，谋吕布等大奖静候有缘人。",
        "孙邵", None, "谋吕布", "神甘宁"),
    box("xinghuo_2025", "2025年星火燎原", 2025, "星火燎原", "2025-05-31", 200, "crimson",
        "星火燎原，势不可挡。200 元宝一抽，谋曹丕等大奖静候有缘人。",
        "孙邵", None, "谋曹丕", "神甘宁"),
    box("lieyan_2025", "2025年烈炎仁心", 2025, "烈炎仁心", "2025-05-17", 200, "crimson",
        "烈炎仁心，刚柔并济。200 元宝一抽，神甘宁等大奖静候有缘人。",
        "孙邵", None, "神甘宁", "谋曹丕"),
    box("shenya_2025", "2025年神鸦显圣", 2025, "神鸦显圣", "2025-05-01", 200, "gold",
        "神鸦显圣，天命所归。200 元宝一抽，神甘宁等大奖静候有缘人。",
        "孙邵", None, "神甘宁", "谋曹丕"),
    box("dangping_2025", "2025年荡平淮南", 2025, "荡平淮南", "2025-04-04", 200, "azure",
        "荡平淮南，威震东南。200 元宝一抽，谋曹丕等大奖静候有缘人。",
        "孙邵", None, "谋曹丕", "神甘宁"),
    box("suiyou_2025", "2025年岁友同欢", 2025, "岁友同欢", "2025-03-01", 200, "plum",
        "岁友同欢，其乐融融。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "孙邵", None, "势董昭", "谋关羽"),
    box("xiangshe_2025", "2025年祥蛇纳福", 2025, "祥蛇纳福", "2025-01-28", 200, "gold",
        "祥蛇纳福，灵蛇献瑞。200 元宝一抽，势太史慈等大奖静候有缘人。",
        "孙邵", None, "势太史慈", "谋关羽"),
    box("lingshe_2025", "2025年灵蛇献瑞", 2025, "灵蛇献瑞", "2025-01-17", 200, "gold",
        "灵蛇献瑞，瑞气盈门。200 元宝一抽，势太史慈等大奖静候有缘人。",
        "孙邵", None, "势太史慈", "谋关羽"),
    # ============================================================ 2024
    box("bixue_2024", "2024年碧血丹心", 2024, "碧血丹心", "2024-11-23", 200, "crimson",
        "碧血丹心，忠义千秋。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "贾充", None, "SP甄姬", "谋关羽"),
    box("jilve_2024", "2024年极略鬼才", 2024, "极略鬼才", "2024-09-13", 200, "azure",
        "极略鬼才，智计百出。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "贾充", None, "谯周", "谋关羽"),
    box("zhimou_2024", "2024年智谋百变", 2024, "智谋百变", "2024-08-31", 200, "plum",
        "智谋百变，随机应变。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "贾充", None, "神司马懿", "谋关羽"),
    box("shengshi_2024", "2024年盛世芳华", 2024, "盛世芳华", "2024-07-13", 200, "crimson",
        "盛世芳华，国色天香。200 元宝一抽，曹髦等大奖静候有缘人。",
        "贾充", None, "曹髦", "谋关羽"),
    box("guose_2024", "2024年国色天香", 2024, "国色天香", "2024-07-13", 200, "plum",
        "国色天香，倾国倾城。200 元宝一抽，曹髦等大奖静候有缘人。",
        "贾充", None, "曹髦", "谋关羽"),
    box("zongqing_2024", "2024年粽情端阳", 2024, "粽情端阳", "2024-06-08", 200, "azure",
        "粽情端阳，龙舟竞渡。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "贾充", None, "谋夏侯惇", "谋关羽"),
    box("gongxiang_2024", "2024年共襄盛诞", 2024, "共襄盛诞", "2024-05-01", 200, "crimson",
        "共襄盛诞，普天同庆。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "贾充", None, "神鲁肃", "谋关羽"),
    box("longyou_2024", "2024年龙游天下", 2024, "龙游天下", "2024-02-09", 200, "gold",
        "龙游天下，海阔天空。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "贾充", None, "谋曹丕", "谋关羽"),
    box("longtengsihai_2024", "2024年龙腾四海", 2024, "龙腾四海", "2024-02-02", 200, "gold",
        "龙腾四海，威震八方。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "贾充", None, "谋曹丕", "谋关羽"),
    box("longtengwanli_2024", "2024年龙腾万里", 2024, "龙腾万里", "2024-02-02", 200, "gold",
        "龙腾万里，前程似锦。200 元宝一抽，谋关羽等大奖静候有缘人。",
        "贾充", None, "谋诸葛亮", "谋关羽"),
]


def build(report: bool) -> None:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    existing_ids = {b["id"] for b in raw["boxes"]}
    new_ids = {b["id"] for b in NEW_BOXES}
    dup = existing_ids & new_ids
    if dup:
        print(f"警告：以下 id 已存在，跳过：{dup}")
    to_add = [b for b in NEW_BOXES if b["id"] not in existing_ids]

    if report:
        for b in to_add:
            tops = sorted(b["pool"], key=lambda e: e["weight"])[:3]
            top_text = " / ".join(f"{t['name']} {t['probability']}%" for t in tops)
            print(f"{b['year']} {b['name']:<14} {b['price']:>3} 元宝  "
                  f"顶级 {top_text}")
        print(f"\n将新增 {len(to_add)} 只，现有 {len(raw['boxes'])} 只 -> 共 {len(raw['boxes']) + len(to_add)} 只")
        return

    merged = raw["boxes"] + to_add
    merged.sort(key=lambda b: (b.get("year", 2026), b.get("released", "2026-12-31")), reverse=True)
    DATA.write_text(
        json.dumps({"boxes": merged}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"写入 {DATA.name}：新增 {len(to_add)} 只，共 {len(merged)} 只盒子")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    build(args.report)
    sys.exit(0)
