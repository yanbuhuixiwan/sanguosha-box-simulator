from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .lock import WRITE_LOCK
from .gacha import (
    box_entries,
    boxes_catalog,
    corridor_draw_entries,
    corridor_episode,
    palace_entries,
    palace_grand_probability,
    palace_groups,
    palace_pool,
    recruit_pool,
)
from .models import init_db
from .routers import auth, boxes, collection, corridor, palace, recruit, shop


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="三国杀移动版盒子模拟器 · 纯娱乐，不涉及任何真实充值",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, boxes, recruit, collection, shop, palace, corridor):
    app.include_router(module.router, prefix=settings.API_PREFIX)


@app.middleware("http")
async def serialize_api(request: Request, call_next):
    """把 API 请求排成队，避免并发「读-改-写」互相覆盖（SQLite 只有一个写者）。

    素材图（/api/media）不进队列：一页几十张图并发取，串起来会把页面拖慢；
    它们只读静态文件，不参与账目。
    """
    if request.url.path.startswith(f"{settings.API_PREFIX}/media"):
        return await call_next(request)
    async with WRITE_LOCK:
        return await call_next(request)

# 素材图（武将/皮肤/道具）直接由后端托管，前端用 /api/media/<相对路径> 取图。
# 放在 /api 下是为了同时被 run.py 与 nginx 的 /api 反代覆盖，不必再改部署配置。
if settings.IMAGE_DIR.is_dir():
    app.mount("/api/media", StaticFiles(directory=str(settings.IMAGE_DIR)), name="media")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/api/meta")
def meta():
    return {
        "app": settings.APP_NAME,
        "max_bulk_open": settings.MAX_BULK_OPEN,
        "initial_yuanbao": settings.INITIAL_YUANBAO,
        "recharge_step": settings.RECHARGE_STEP,
        "disclaimer": "本模拟器仅用于概率演示与娱乐，所有元宝、道具均为虚拟数据，不可兑换任何真实物品。",
    }


@app.get("/api/odds")
def odds():
    """公开概率公示，无需登录。"""
    catalog = []
    for box in boxes_catalog():
        item = {k: v for k, v in box.items() if k != "pool"}
        item["entries"] = sorted(
            box_entries(box), key=lambda e: e["probability"], reverse=True
        )
        item["entry_count"] = len(box["pool"])
        catalog.append(item)

    return {
        "boxes": catalog,
        "pools": [recruit_pool("hero"), recruit_pool("skin")],
        "palace": {
            **{k: v for k, v in palace_pool().items() if k != "grid"},
            "entries": palace_entries(palace_pool(), 0),
            "groups": palace_groups(palace_pool(), 0),
            "base_grand_probability": palace_grand_probability(palace_pool(), 0),
            "max_grand_probability": palace_grand_probability(
                palace_pool(), int(palace_pool()["pity_limit"])
            ),
        },
        "corridor": {
            **{
                k: v
                for k, v in corridor_episode().items()
                if k not in ("fragments", "lines", "draw_pool", "line_rewards")
            },
            "entries": corridor_draw_entries(corridor_episode()),
        },
    }
