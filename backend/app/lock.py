"""请求串行化用的异步锁。

SQLite 只有一个写者，而 FastAPI 的依赖注入阶段（`current_user`）就已经开了读事务。
两个请求同时「读元宝 → 扣费 → 写回」时，后提交的会覆盖前一次结果（lost update），
表现为「并发抽奖发了奖励却没扣道具」，或者直接撞上 `database is locked`。

这里用一把全局异步锁，在 HTTP 中间件层把请求排队（静态素材除外），这样读事务
天然落在锁内、读到的永远是最新已提交数据。

为什么是 asyncio.Lock 而不是 threading.Lock：
FastAPI 的 yield 依赖（get_db）由 anyio 在线程池里执行退出逻辑，可能换线程，
threading 的 RLock 跨线程释放会直接抛 "cannot release un-acquired lock"。
"""
from __future__ import annotations

import asyncio

WRITE_LOCK = asyncio.Lock()
