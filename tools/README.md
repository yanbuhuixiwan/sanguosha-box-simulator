# tools/ —— 素材抓取与索引

从《三国杀移动版》官网 + 哔哩哔哩 wiki 直接抓素材，替代一张张截图。只用公开页面，无需登录。

## 数据源

| 用途 | 地址 | 说明 |
| --- | --- | --- |
| 武将清单 | `https://www.sanguosha.cn/pc/hero-list.html` | 583 个名字 / 588 个 id（个别武将有两个 id） |
| 武将原画 + 皮肤 | `https://www.sanguosha.cn/pc/hero-detail-<id>.html` | swiper 里第 1 张是原画，其后是该武将的皮肤；无边框无水印 |
| 高清皮肤 | `https://share.sanguosha.cn/api/skins/list?type=<1\|2\|3>&limit=200` | 皮肤绘影堂接口，`inner_banner` 为 1920×1305 高清横向原画；注意数据在 `data.lists.data` |
| **皮肤名** | `https://wiki.biligame.com/msgs/<武将>` | wiki 的「皮肤名 / 画师 / 品质」表，字段就是游戏内官方皮肤名 |
| **招募权重** | `https://www.sanguosha.cn/news/detail/7.html` | 武将招募权重公示：武将名称 / 武将分级(1~20) / 权重，217 名 |
| **皮肤收集权重** | `https://www.sanguosha.cn/news/detail/9.html` | 皮肤收集权重公示：正文长图（1030×9386），543 款皮肤的 分级 / 权重 |

详情页图片有两种写法（新将相对路径 `/storage/uploads/images/87000.png`、老将绝对路径 `.../images/skins/7400.jpg`），脚本都认。

**为什么皮肤名必须靠 wiki**：官网详情页 `alt` 全为空、绘影堂接口的 `name` 字段又与武将名混在一起，官网侧没有任何「这张图叫什么」的文本。wiki 是玩家维护的，皮肤名与游戏内一致，可与官网图互补。

**wiki 抓取的两个坑**：
1. 请求必须带 `Referer: https://wiki.biligame.com/msgs/` 和浏览器 UA，否则 HTTP 567。
2. 部分缩略图写成 `[[File:xxx.jpg@x350px@center@class=tooltip-content@link=]]`，文件名要在第一个 `@` 处截断，否则 imageinfo 查不到（早期因此误判 51 张「无图」）。

## 命名规则（重要）

- **前缀一律保留**：`严颜` / `界严颜`、`姜维` / `神姜维`、`小乔` / `势小乔` 都是不同武将，各自独立条目，绝不合并。
- 只去掉分隔符「·」（`势·小乔` → `势小乔`）和 Windows 非法字符；`*` 转全角 `＊`。
- 同名不同 id（`孔融` `糜夫人` `陈武董袭` `蒋钦` `吕范`）会把两个 id 的图合并进同一目录，第二张起加 `_2`。
- **皮肤统一命名 `<武将>_<皮肤名>.jpg`**，例如 `灵雎_霜刃绚练.jpg`、`小乔_采莲江南.jpg`。

## 用法

```bash
python tools/fetch_sgs_assets.py heroes --all        # 全部 588 id（已有文件自动跳过，可反复跑）
python tools/fetch_sgs_assets.py heroes 王凌 阮慧     # 指定武将；异体字 祇/祗 自动纠正
python tools/fetch_sgs_assets.py heroes --from-boxes  # 只抓 boxes.json 里出现的
python tools/fetch_sgs_assets.py skins               # 绘影堂全部 129 张（约 338MB）
python tools/fetch_sgs_assets.py skins 心宇同一       # 按皮肤名/武将名过滤

python tools/fetch_wiki_skins.py                     # 按 wiki 皮肤表带名字下载（已有文件跳过）
python tools/fetch_wiki_skins.py --names 灵雎 界严颜   # 只跑指定武将
python tools/fetch_wiki_skins.py --repair            # 只补 wiki_skins.json 里失败的条目
python tools/fetch_wiki_skins.py --owners            # 生成 武将→皮肤 归属表

python tools/prepare_assets.py                       # 整理：武将原画归位 + 绘影堂皮肤统一命名
python tools/prepare_assets.py --dry-run             # 只统计会补多少张，不写文件

python tools/build_index.py                          # 生成 index.html + 两份 CSV
python tools/build_recruit_pools.py                   # 按官方公示重建 heroes.json / skins.json
python tools/build_recruit_pools.py --report          # 只看分档统计与缺图
python tools/build_media_map.py                      # 生成前端查图用的 media-map.json
python tools/patch_corridor_diag.py                  # 给 77 期回廊逐期写 diag_reward（对角皮肤，每期 1 个）
python tools/import_corridor_diag.py                # 按 data/corridor_diag.csv（或 corr-77=皮肤·武将）导入真实对角皮肤
python tools/build_corridor_lines.py                 # 按实拍模板重建每期外圈 12 格连线奖励（line_rewards）
python tools/build_corridor_lines.py --report         # 只看每期分到模板 A 还是 B
python tools/repair_corridor_periods.py               # 体检：官方清单里有、corridor.json 里缺的期次
python tools/repair_corridor_periods.py --write       # 补进去（已有的期一个字段都不动）

python tools/make_activity_icons.py                  # 自绘「天工石 / 迷迭珠」图标（官方没有独立图）
node tools/shot.mjs <token> <输出目录> /palace        # headless Chrome 截图，验收页面用
```

> 改完 `image/` 或 `backend/app/data/*.json` 里的卡池，**必须**重跑 `build_media_map.py` 再 `npm run build`，
> 否则前端查不到新名字的图。

都支持 `--dry-run`（只出清单不下载）与 `--workers N`（默认 6~8）。

## 产出结构

```
image/
├─ 武将图片/                      # 584 张武将原画，命名 <武将>.png/jpg，前缀保留
├─ 皮肤图片/                      # 1312 张带名皮肤，命名 <武将>_<皮肤名>.jpg
├─ 道具图片/                      # 10 张
├─ index.html                     # 本地可搜索画廊（双击打开，无需服务器）
├─ 素材清单.csv                   # 分类/武将/皮肤名/分辨率/大小/路径
├─ 皮肤归属表.csv                 # 武将/皮肤数/皮肤名/图片文件（含共用图）
└─ 官网素材/                      # 抓取原始产物与中间清单
   ├─ 武将/<武将名>/<武将名>_1.jpg  # _1 = 原画，_2.._n = 该将的皮肤
   ├─ 皮肤/<皮肤名>＊<武将>.jpg      # 绘影堂 1920×1305 高清
   ├─ 低清弃用/                    # 同名低分辨率副本（保留备查，未删）
   └─ heroes.json / skins.json / wiki_skins.json / skin_owners.json
```

索引页支持 `?f=皮肤图片&h=小乔&q=采莲` 直接定位；点卡片下方红色武将名可按该武将筛选。

## 关于「界/势/谋/神/SP 版本将的皮肤」

wiki 上这些版本将的页面确实列了皮肤表，但表里 `title` 写的是**基础武将名**
（界关羽页写的是「过关斩将*关羽」）。所以：

- 图片文件只存一份，归在基础将名下（`关羽_过关斩将.jpg`）；
- `皮肤归属表.csv` / `skin_owners.json` 按「页面属于谁」记录归属，
  于是 `界关羽` 有 13 条、`势小乔` 有 10 条、`界严颜` 有 2 条自己的清单，指向同一批文件。

这样既满足「每位武将都有自己的皮肤清单」，又不会为同一张图重复占几百 MB。

## 道具图标从哪来

游戏内道具图标官网没有公开目录，只能从 wiki 的道具页 / 道具图鉴取（88×88 透明 PNG，够 2 倍屏用）：

| 道具 | 来源 | 备注 |
| --- | --- | --- |
| 招募令 雁翎 将魂 换将卡 手气卡 点将卡 菜篮子 欢乐豆 史诗体验卡 心愿积分 | 早期手切，256×256 | 带实拍底色 |
| 雁翎甲 / 进阶丹 / 史诗宝珠碎片 | wiki `道具图鉴` 页 | 88×88 原图，`@` 后缀坑同上 |
| **史诗宝珠** | **自制** | 全站（官网 / msgs wiki / sgsol wiki / 文件命名空间）都没有这张图，按碎片的玉色画了一颗同色系玉珠，`image/道具图片/史诗宝珠.png` |

判断某个道具缺图的办法：跑 `build_media_map.py`，末尾会打印各分类的缺图名单。

同一个图标下的不同叫法写在 `build_media_map.py` 的 `ITEM_ALIAS` 里（现在只有 `一堆银币 -> 银币`）。
**别直接手改 `media-map.json`**——它是生成物，下次重跑就没了。

## 卡池数据的两个坑（已修）

- `backend/app/data/heroes.json` 里原有两个不存在的武将 `SP甘宁`、`SP诸葛亮`——官网与 wiki 均无此将，
  已换成 `SP庞德`、`SP徐庶`（同为 SP·叁 档）。
- `skins.json` 原来 34 个皮肤名里有 28 个是素材库里查不到的（如 `虎啸龙吟·张飞`、`白衣渡江·陆逊`），
  已按 wiki 品质重建成 31 个真实存在的皮肤（普通 10 / 稀有 8 / 史诗 6 / 传说 4 / 典藏动态 3），权重不变。
  `boxes.json` 里那张 `碧海生潮·司马徽动态包` 当时也查不到，先换成了 `龙兴凤举·司马徽动态包`；
  **2026-10-21 已从手机版公共资源 CDN 补回真图**（见下「新皮肤没图怎么办」）。

## 新皮肤没图怎么办（2026-10 补的第四条路）

绘影堂 `share.sanguosha.cn/api/skins/list` 只收 **145 款**重点皮（至尊/传说），wiki 也不收当月新皮，
官网 `hero-detail` 的皮肤 swiper 常年不更新。当月新皮肤可以从**手机版公共资源 CDN** 直接取：

```
https://sjpubicres.sanguosha.cn/release/character_skins/char/<武将id>_<序号>.jpg
```

- `<武将id>` 就是官网 `hero-list.html` 里 `pic_index/<id>.png` 的那个 id（司马徽 = 30014）。
- `<序号>` 从 1 试起，通常只有 `_1` 存在（当前在售皮肤的立绘）；**530×750、右下角带「三国杀 m.sanguosha.cn」淡水印**。
- 怎么找到这个 URL：官方社区「三国咸话」`xianhua.sanguosha.cn` 的皮肤赏析/爆料帖正文里，
  图片就是这条 CDN 链接（例：`postDetails?id=12667719` → `30014_1.jpg` = `碧海生潮*司马徽`、`393_1.jpg` = `翱宇论天*秦宓`）。
  帖子里同时出现两张新皮时，按「武将 id ↔ 武将名」对号入座即可，别按出现顺序猜。
- 同理，wiki 的 `allimages?aimprefix=<皮肤名>` 比全文搜索准（`蛇年中秋-甘夫人-静态.jpg` 就是搜索搜不到、前缀能搜到的）。

## 现状（2026-10-21）

- 武将原画：**599 张**（含 `_头像` 9 张、双 id 的 `_2`/`_3` 5 张）。
  官网详情页图片区为空、确实没有原画的 14 位：
  `何进` `牛金` `韩遂` `甘夫人` `谋·周瑜` `霍峻` `张布` `笮融` `势·钟会` `势·王昶` `SP于禁` `朱绩` `马腾` `司马伷`
  （其中 `朱绩` `马腾` 的详情页直接 500，是官网自己的 bug；`韩遂` 已从 wiki 补到 530×750 原画）
- 带名皮肤：**1333 张**，wiki 表覆盖 1301 条（383 位武将），绘影堂 145 款里 33 款为 wiki 未收录。
- 道具图标：**19 张**（`media-map` 里 20 个键，`一堆银币` 复用 `银币.png`）。
  游戏卡池里仍走字形兜底的都是「礼盒限定道具」：各期武将碎片 7 种 + `桃园结义/古城相会皮肤包`。
- 皮肤归属：**533 / 573 位武将**有皮肤清单，共 **2204 条**，仅 1 条无对应图。
- 剩余缺口：**40 位武将 wiki 无皮肤表**（多为新将/SP/势系列，如 `SP公孙瓒` `崔芙` `势周瑜` `神马超`）；
  **3 位有皮肤清单但无独立原画**（`伊籍` `刘赪` `杨婉`，官网详情页确实没图）。
- 头像没做批量：官网原画多为全身构图，自动裁出来的头肩像质量参差（骑射类构图脸太小），需要时按名单单独裁。

## 分辨率取舍

- 官网武将原画多为 **530×750**，个别新将 1080×1528 / 1000×1075 / 2480×3508；手机截图裁出来是 872×1236 但带「三国杀 / sanguosha.com」水印与卡框。
- 绘影堂皮肤 **1920×1305**；wiki 缩略图统一 900px 宽（`iiurlwidth=900`）。
- 手机版 CDN 的皮肤立绘是竖版 **530×750** 且带淡水印（目前只有 `司马徽_碧海生潮` 一张走这条路），
  其余皮肤仍是 750×530 横版——卡片按 `object-fit: cover` 裁方形，混排不会破版。
- 同一皮肤两处都有时保留绘影堂版（1920×1305），wiki 版移到 `官网素材/低清弃用/`。

## 截图脚本（`shot.mjs`）

`tools/shot.mjs` 用 Chrome headless + CDP 打开本地站点、注入登录态并整页截图，只在本地验收时用，不参与构建。

```bash
# token 从登录接口拿：POST /api/auth/login → { token }
node tools/shot.mjs "$TOKEN" docs/screenshots/tmp /palace /corridor

# 支持「先进页面再点一次」：/palace|.btn-gold 会点十连按钮，用来截结算弹窗
node tools/shot.mjs "$TOKEN" docs/screenshots/tmp '/palace|.palace-hero__side .btn-gold'

# 窄屏（390×844）检查移动端
MOBILE=1 node tools/shot.mjs "$TOKEN" docs/screenshots/tmp /palace
```

Git Bash 下传 `/palace` 会被 MSYS 改写成 Windows 路径，命令前加 `MSYS_NO_PATHCONV=1`。

## 元素裁剪截图（`el_shot.mjs`）

`shot.mjs` 只能拍首屏（滚到下方的阵盘、详情区会被截断）。`tools/el_shot.mjs` 先滚到目标元素，再用
`Page.captureScreenshot` 的 `clip` 按元素外框拍——验收「阵盘拼图」「详情面板」这类局部区块时用它。

```bash
# 只拍 5×5 阵盘本身（默认选择器是 .board-stage 整块面板）
node tools/el_shot.mjs "login:用户名:密码" "/corridor?period=corr-72" docs/qa/board.png ".board"

# 桌面宽度（默认按 390×900 移动端渲染）
MOBILE=0 node tools/el_shot.mjs "$TOKEN" /palace docs/qa/palace.png ".palace-grid"
```

要点：`clip` 用的是**文档坐标**，所以元素 `getBoundingClientRect()` 要加 `scrollX/scrollY`，并且必须开
`captureBeyondViewport`，否则滚出视口的部分会拍成空白。

## 自绘道具图标（`make_activity_icons.py`）

「天工石」「迷迭珠」官方没有单独放出图标，脚本按活动主色用 PIL 画一枚（青玉矿石 + 金纹 / 紫玉珠 + 金环），
输出 256×256 RGBA PNG 到 `image/道具图片/`。改配色直接改脚本里的色值，重跑即可；跑完记得再跑一次
`build_media_map.py`。
python tools/build_past_boxes.py                     # 按官网公示图重建往期 20 只礼盒并合入 boxes.json
python tools/build_past_boxes.py --report            # 只打印每只盒的权重/概率校验
