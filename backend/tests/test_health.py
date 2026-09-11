"""健康检查端点测试:
- DB + Redis 正常 → 200 ok
- Redis 挂了 → 200 degraded(软依赖,服务仍可用,不触发容器重启)
- DB 挂了 → 503 unhealthy(硬依赖)
"""
import httpx

from app.main import app


async def _call_health() -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.get("/health")


def _patch_db(monkeypatch, ok: bool):
    from app.routers import health as health_mod

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, *args, **kwargs):
            if not ok:
                raise ConnectionError("db down")
            return None

    monkeypatch.setattr(health_mod, "AsyncSessionLocal", lambda: _FakeSession())


def _patch_redis(monkeypatch, ok: bool):
    from app.routers import health as health_mod

    class _FakeRedis:
        async def ping(self):
            if not ok:
                raise ConnectionError("redis down")
            return True

    monkeypatch.setattr(health_mod, "get_redis", lambda: _FakeRedis())


async def test_health_all_ok(monkeypatch):
    """DB + Redis 正常 → 200 ok"""
    _patch_db(monkeypatch, ok=True)
    _patch_redis(monkeypatch, ok=True)
    r = await _call_health()
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "redis": "ok"}


async def test_health_redis_down_is_degraded(monkeypatch):
    """Redis 挂了 → 200 degraded(软依赖,不应让容器判定为不健康)"""
    _patch_db(monkeypatch, ok=True)
    _patch_redis(monkeypatch, ok=False)
    r = await _call_health()
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"].startswith("error:")


async def test_health_db_down_is_unhealthy(monkeypatch):
    """DB 挂了 → 503 unhealthy(硬依赖)"""
    _patch_db(monkeypatch, ok=False)
    _patch_redis(monkeypatch, ok=True)
    r = await _call_health()
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unhealthy"
    assert body["checks"]["database"].startswith("error:")


async def test_request_id_header(monkeypatch):
    """响应头带 X-Request-Id 与 X-Process-Time(便于排障对照)"""
    _patch_db(monkeypatch, ok=True)
    _patch_redis(monkeypatch, ok=True)
    r = await _call_health()
    assert r.headers.get("x-request-id")
    assert r.headers.get("x-process-time")


async def test_request_id_passthrough(monkeypatch):
    """客户端传入 X-Request-Id 时复用(便于前端错误与后端日志关联)"""
    _patch_db(monkeypatch, ok=True)
    _patch_redis(monkeypatch, ok=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/health", headers={"x-request-id": "trace-abc-123"})
    assert r.headers["x-request-id"] == "trace-abc-123"
