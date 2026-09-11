"""请求日志中间件:记录每个请求的方法/路径/状态码/耗时/客户端 IP,并注入请求 ID。

用途(线上排障):
- 出问题时能看到"谁、什么时候、调了哪个接口、耗时多少、结果如何";
- 每个请求分配 request_id,响应头回传 X-Request-Id,便于与前端报错/日志对照;
- 响应头 X-Process-Time 便于快速定位慢接口。

日志级别:5xx=ERROR,4xx=WARNING,其余=INFO;/health 探活请求降为 DEBUG(避免刷屏)。
"""
import logging
import time
import uuid

from fastapi import Request

logger = logging.getLogger("uvicorn.error")

# 不记录访问日志的路径(容器 healthcheck 每 10s 一次,会刷屏)
_QUIET_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        # 未捕获异常:记录后抛出,由全局异常处理器返回统一响应
        cost = (time.perf_counter() - start) * 1000
        logger.exception("请求异常 %s %s rid=%s %.1fms",
                         request.method, request.url.path, request_id, cost)
        raise

    cost = (time.perf_counter() - start) * 1000
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Process-Time"] = f"{cost:.1f}"

    # 客户端 IP(经 nginx 反代时取真实 IP)
    forwarded = request.headers.get("x-forwarded-for")
    client = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "-")

    query = f"?{request.url.query}" if request.url.query else ""
    line = (f"{request.method} {request.url.path}{query} {response.status_code} "
            f"{cost:.1f}ms ip={client} rid={request_id}")

    if request.url.path in _QUIET_PATHS:
        logger.debug(line)
    elif response.status_code >= 500:
        logger.error(line)
    elif response.status_code >= 400:
        logger.warning(line)
    else:
        logger.info(line)

    return response
