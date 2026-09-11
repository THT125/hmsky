"""系统健康检查(容器 healthcheck / 负载均衡探活,不鉴权)

设计说明:
- **MySQL 是硬依赖**:连不上 → 返回 503,容器标记为不健康;
- **Redis 是软依赖**:连不上 → 仍返回 200(status=degraded),因为本项目对 Redis
  全程降级(缓存直查库、会话放行),Redis 挂了业务照跑,不应触发容器重启;
- 响应**不使用** {code,msg,data} 包装:健康检查是基础设施约定,负载均衡只看 HTTP 状态码。
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["系统"])


@router.get("/health")
async def health():
    """
    健康检查:探测 MySQL 与 Redis 连通性

    返回:
    - HTTP 200:status=ok(全部正常)/ status=degraded(Redis 异常但服务可用)
    - HTTP 503:status=unhealthy(MySQL 不可用)
    """
    checks = {}

    # MySQL(硬依赖)
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error:{type(e).__name__}"
        logger.warning("健康检查:数据库不可用 %s", e)

    # Redis(软依赖:挂了自动降级)
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error:{type(e).__name__}"
        logger.warning("健康检查:Redis 不可用(服务降级运行) %s", e)

    db_ok = checks["database"] == "ok"
    redis_ok = checks["redis"] == "ok"
    if not db_ok:
        status = "unhealthy"
    elif not redis_ok:
        status = "degraded"
    else:
        status = "ok"

    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"status": status, "checks": checks},
    )
