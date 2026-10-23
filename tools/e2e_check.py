"""端到端自检：把后端所有接口真跑一遍，检查业务不变量。

用法：python tools/e2e_check.py [base_url]
默认打 http://127.0.0.1:8000/api，会新建一个 e2e_<时间戳> 账号，不动已有数据。
输出里 FAIL / WARN 是需要关注的行。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api").rstrip("/")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = ""
FAILS: list[str] = []
WARNS: list[str] = []


def call(method: str, path: str, body=None, expect=200, auth=True, quiet=False):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if auth and TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with OPENER.open(req, timeout=30) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = e.code
    except Exception as e:  # 连接失败等
        FAILS.append(f"{method} {path} -> 请求异常 {e!r}")
        return None, 0
    try:
        payload = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        payload = raw.decode("utf-8", "replace")
    if status != expect:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        FAILS.append(f"{method} {path} -> HTTP {status}（期望 {expect}）{detail!r}")
    elif not quiet:
        print(f"  ok  {method:5s} {path}")
    return payload, status


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)


def warn(cond: bool, msg: str) -> None:
    if not cond:
        WARNS.append(msg)


def pct_sum(entries) -> float:
    return round(sum(float(e.get("probability", 0)) for e in entries), 3)


def main() -> None:
    global TOKEN
    print("== 0. 健康检查 ==")
    health, _ = call("GET", "/health", auth=False)
    check(isinstance(health, dict) and health.get("status") == "ok", "health 返回异常")

    print("== 1. 账号：注册 / 登录 / me / 充值 ==")
    user = f"e2e_{int(time.time())}"
    reg, _ = call("POST", "/auth/register", {"username": user, "password": "test1234", "nickname": "自检"}, auth=False)
    if not reg or "token" not in reg:
        print("注册失败，终止")
        report()
        return
    TOKEN = reg["token"]
    check(reg["user"]["yuanbao"] >= 0, "注册返回的元宝异常")

    dup, _ = call("POST", "/auth/register", {"username": user, "password": "test1234"}, expect=409, auth=False)
    bad, _ = call("POST", "/auth/login", {"username": user, "password": "wrong"}, expect=401, auth=False)
    call("POST", "/auth/login", {"username": user, "password": "test1234"}, auth=False)

    me, _ = call("GET", "/me")
    check(isinstance(me, dict) and me.get("username") == user, "me 返回的用户不对")

    recharged, _ = call("POST", "/me/recharge", {"amount": 1000000})
    check(recharged and recharged.get("yuanbao") == me["yuanbao"] + 1000000, "充值后余额不对")
    base_yb = recharged["yuanbao"] if recharged else 0

    print("== 2. 盒子（74 只）==")
    cat, _ = call("GET", "/boxes")
    boxes = cat["boxes"] if cat else []
    check(len(boxes) >= 70, f"盒子数量偏少：{len(boxes)}")
    bulk = cat.get("max_bulk_open") if cat else 0
    check(bulk and bulk >= 10, f"max_bulk_open 异常：{bulk}")
    bad_odds, bad_price, empty = [], [], []
    for b in boxes:
        s = pct_sum(b["entries"])
        if abs(s - 100) > 0.05:
            bad_odds.append((b["id"], s))
        if not b.get("price") or b["price"] <= 0:
            bad_price.append(b["id"])
        if not b["entries"]:
            empty.append(b["id"])
    check(not bad_odds, f"概率和不为 100% 的盒子：{bad_odds[:5]}")
    check(not bad_price, f"价格缺失的盒子：{bad_price[:5]}")
    check(not empty, f"奖池为空的盒子：{empty[:5]}")
    check(all(b.get("entries") for b in boxes), "有盒子奖池为空")


    one, _ = call("POST", "/boxes/e2e-none/open", {"count": 1}, expect=404)
    # 每个盒子各开一次（含往期 / 半价）
    total_cost = 0
    for b in boxes:
        res, st = call("POST", f"/boxes/{b['id']}/open", {"count": 1}, quiet=True)
        if st != 200:
            continue
        total_cost += res["cost"]
        if len(res.get("results", [])) != 1:
            FAILS.append(f"开盒 {b['id']} 返回结果条数 {len(res.get('results', []))}")
        if res.get("yuanbao", 0) != base_yb - total_cost:
            FAILS.append(f"开盒 {b['id']} 后余额 {res.get('yuanbao')} 与预期 {base_yb - total_cost} 不符")
    print(f"  ok  逐只开盒 {len(boxes)} 次，花费 {total_cost} 元宝")

    ten, _ = call("POST", f"/boxes/{boxes[0]['id']}/open", {"count": 10})
    check(ten and len(ten.get("results", [])) == 10, "十连开盒结果条数不为 10")
    big, _ = call("POST", f"/boxes/{boxes[0]['id']}/open", {"count": 999}, expect=400)
    zero, _ = call("POST", f"/boxes/{boxes[0]['id']}/open", {"count": 0}, expect=422)

    print("== 3. 招募 ==")
    for pool_id in ("hero", "skin"):
        pool, _ = call("GET", f"/recruit/{pool_id}")
        check(pool and abs(pct_sum(pool["entries"]) - 100) < 0.05, f"{pool_id} 卡池概率和不为 100")
        # 招募令靠商店补
        call("POST", "/shop/buy", {"item_key": "token_1", "count": 50}, quiet=True)
        call("POST", "/shop/buy", {"item_key": "armor_1", "count": 50}, quiet=True)
        res, st = call("POST", f"/recruit/{pool_id}/pull", {"count": 10}, quiet=True)
        if st == 200:
            check(len(res.get("results", [])) == 10, f"{pool_id} 十连结果条数不为 10")
        else:
            print(f"  !   {pool_id} 十连失败：{res}")
    call("GET", "/recruit/nope", expect=404)

    print("== 4. 商店 ==")
    shop, _ = call("GET", "/shop")
    items = shop["items"] if shop else []
    check(len(items) >= 3, f"商店道具偏少：{len(items)}")
    for it in items:
        res, st = call("POST", "/shop/buy", {"item_key": it["key"], "count": 2}, quiet=True)
        if st == 200:
            if res["owned"] < 2:
                FAILS.append(f"商店买 {it['key']} 后持有量 {res['owned']}")
        else:
            FAILS.append(f"商店买 {it['key']} 失败")
    call("POST", "/shop/buy", {"item_key": "no_such", "count": 1}, expect=404)

    print("== 5. 天宫宝库（9 期）==")
    pal, _ = call("GET", "/palace")
    periods = pal.get("periods", []) if pal else []
    check(len(periods) >= 9, f"天宫期数 {len(periods)}，期望 ≥9")
    check(pal and abs(pct_sum(pal["entries"]) - 100) < 0.05, "天宫奖池概率和不为 100")
    check(pal and not any(e["name"] == "史诗宝珠" for e in pal["entries"]), "天宫奖池仍含史诗宝珠")
    for p in periods:
        detail, st = call("GET", f"/palace?period={p['id']}", quiet=True)
        if st != 200:
            continue
        if abs(pct_sum(detail["entries"]) - 100) > 0.05:
            FAILS.append(f"天宫 {p['id']} 概率和不为 100")
        if len(detail["entries"]) != 12:
            FAILS.append(f"天宫 {p['id']} 格子数 {len(detail['entries'])}，期望 12")
        if p["id"] == pal["id"]:
            check(detail.get("is_current"), "当期 is_current 为假")
        else:
            check(not detail.get("is_current"), f"往期 {p['id']} 的 is_current 为真")
    call("POST", "/palace/pull", {"count": 1, "period": periods[0]["id"]}, expect=400, quiet=True)
    # 当期连抽 10 次（补足天工石）
    call("POST", "/shop/buy", {"item_key": "stone_ti", "count": 50}, quiet=True)
    pres, st = call("POST", "/palace/pull", {"count": 10})
    if st == 200:
        check(len(pres.get("results", [])) == 10, "天宫十连结果条数不为 10")
        check(pres.get("pulls", 0) >= 10, "天宫 pulls 未累加")
        check(pres.get("luck", 0) >= 10, "天宫幸运值未增加")
        check(0 <= pres.get("grand_probability", -1) <= 100, "天宫大奖概率越界")

    print("== 6. 梦之回廊（77 期，逐期回想）==")
    cor, _ = call("GET", "/corridor")
    periods = cor.get("periods", []) if cor else []
    check(len(periods) == 77, f"回廊期数 {len(periods)}，期望 77")
    if cor:
        check(cor["total_fragments"] == 25, f"阵盘碎片数 {cor['total_fragments']}，期望 25")
        check(cor["total_lines"] == 12, f"连线数 {cor['total_lines']}，期望 12")
        check(abs(pct_sum(cor["draw_entries"]) - 100) < 0.05, "回廊奖池概率和不为 100")
        check(len(cor["draw_entries"]) == 11, f"回廊奖池项数 {len(cor['draw_entries'])}，期望 11")
        check(cor["pity_limit"] in (120, 150, 180, 250, 500, 600), f"当期保底 {cor['pity_limit']}")
    pities = {}
    bad = []
    for p in periods:
        d, st = call("GET", f"/corridor?period={p['id']}", quiet=True)
        if st != 200:
            bad.append(p["id"])
            continue
        pities[d["pity_limit"]] = pities.get(d["pity_limit"], 0) + 1
        if abs(pct_sum(d["draw_entries"]) - 100) > 0.05:
            FAILS.append(f"回廊 {p['id']} 奖池概率和不为 100")
        if len(d["board"]) != 25:
            FAILS.append(f"回廊 {p['id']} 格子数 {len(d['board'])}")
        if len(d["lines"]) != 12:
            FAILS.append(f"回廊 {p['id']} 连线数 {len(d['lines'])}")
        if not d.get("pity_limit"):
            FAILS.append(f"回廊 {p['id']} 缺保底抽数")
    check(not bad, f"回廊读不出来的期次：{bad[:5]}")
    print(f"  保底分布：{dict(sorted(pities.items()))}")
    check(set(pities) <= {120, 150, 180, 250, 500, 600}, f"出现异常的保底抽数：{set(pities)}")
    check(len(pities) >= 3, f"保底档位只有 {sorted(pities)}，应有 250/500/600 等多档")

    # 77 期逐期各 1 颗 + 一期打到保底，买够 500 颗
    for _ in range(6):
        call("POST", "/shop/buy", {"item_key": "bead_mi", "count": 99}, quiet=True)
    bad_recall = []
    for p in periods:
        res, st = call("POST", "/corridor/recall", {"count": 1, "period": p["id"]}, quiet=True)
        if st != 200:
            bad_recall.append((p["id"], res.get("detail") if isinstance(res, dict) else res))
            continue
        if res.get("pulls") != 1:
            FAILS.append(f"回廊 {p['id']} 首次回想后 pulls={res.get('pulls')}")
        if res.get("lit_count", 0) < 1:
            FAILS.append(f"回廊 {p['id']} 首次回想没点亮任何格")
        if res.get("pity_remaining") != res.get("pity_limit") - 1:
            FAILS.append(f"回廊 {p['id']} 保底剩余计算错误")
    check(not bad_recall, f"往期回想失败的期次：{bad_recall[:5]}")

    # 保底：挑一期 120 抽档，连抽到保底，必须拿到大奖
    target = periods[-1]
    detail, _ = call("GET", f"/corridor?period={target['id']}")
    need = detail["pity_limit"] - detail["pulls"]
    print(f"  验证保底：{target['id']} 还需 {need} 抽")
    guard = 0
    while need > 0 and guard < 700:
        step = min(10, need)
        res, st = call("POST", "/corridor/recall", {"count": step, "period": target["id"]}, quiet=True)
        if st != 200:
            FAILS.append(f"保底连抽失败：{res}")
            break
        need -= step
        guard += step
        if res.get("finished"):
            break
    check(res.get("finished") or res.get("lit_count") == 25, f"抽满保底后未集齐 25 格（lit={res.get('lit_count')}）")
    # 集齐后必须拒绝继续抽（否则白扣迷迭珠）
    extra, st = call("POST", "/corridor/recall", {"count": 1, "period": target["id"]}, expect=400, quiet=True)
    check(isinstance(extra, dict) and "集齐" in str(extra.get("detail", "")), "集齐后仍允许继续抽出")
    print(f"  保底结果：pulls={res.get('pulls')} lit={res.get('lit_count')} finished={res.get('finished')}")

    print("== 7. 背包 / 记录 / 统计 / 分解 ==")
    inv, _ = call("GET", "/inventory")
    check(inv and inv["total"] > 0, "背包为空")
    dup_hero = next((h for h in inv["heroes"] if h["qty"] > 1), None) if inv else None
    if dup_hero:
        d, st = call("POST", "/inventory/decompose", {"key": dup_hero["key"], "count": 1}, quiet=True)
        check(st == 200, f"分解 {dup_hero['name']} 失败")
        if st == 200:
            check(d["qty"] == dup_hero["qty"] - 1, "分解后数量不对")
            check(d["gained"]["qty"] > 0, "分解没有产出将魂")
    else:
        warn(False, "没有重复武将可测分解（本次招募未出重复）")
    dup_skin = next((s for s in inv["skins"] if s["qty"] > 1), None) if inv else None
    if dup_skin:
        call("POST", "/inventory/decompose", {"key": dup_skin["key"], "count": 1}, quiet=True)
    only_one = next((h for h in inv["heroes"] if h["qty"] == 1), None) if inv else None
    if only_one:
        call("POST", "/inventory/decompose", {"key": only_one["key"], "count": 1}, expect=400, quiet=True)

    rec, _ = call("GET", "/records?limit=50")
    check(rec and len(rec.get("records", [])) > 0, "抽取记录为空")
    if rec and rec.get("records"):
        keys = {r.get("source") for r in rec["records"]}
        print(f"  记录来源：{sorted(k for k in keys if k)}")
    call("GET", "/records?source=nope")

    stats, _ = call("GET", "/stats")
    if stats:
        check(stats.get("total_pulls", 0) > 0, "stats 总抽数为 0")
        check(bool(stats.get("by_rarity")), "stats 缺 by_rarity")
        check(bool(stats.get("box_stats")), "stats 缺 box_stats（开过盒子却为空）")
        names = [h["name"] for h in stats.get("highlights", [])]
        check(len(names) == len(set(names)), f"高光时刻有重复道具：{names}")
        print("  stats: pulls=%s by_rarity=%s box_stats=%s" % (
            stats.get("total_pulls"), stats.get("by_rarity"), len(stats.get("box_stats") or [])))
    else:
        FAILS.append("stats 返回为空")

    report()


def report() -> None:
    print("\n================ 结果 ================")
    if WARNS:
        print(f"WARN × {len(WARNS)}")
        for w in WARNS:
            print("  -", w)
    if FAILS:
        print(f"FAIL × {len(FAILS)}")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
