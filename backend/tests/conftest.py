"""pytest 共享 fixture:内存 SQLite 异步数据库会话"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import BigInteger, Integer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# 确保 app 包可导入(backend 根目录)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402,F401  # 注册全部表到 Base.metadata
from app.core.database import Base  # noqa: E402


def _sqlite_compatible_metadata():
    """SQLite 只对 INTEGER PRIMARY KEY 自动自增,将 BigInteger 主键替换为 Integer。
    仅影响测试内存库,不影响生产 MySQL 建表。
    """
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if col.primary_key and isinstance(col.type, BigInteger):
                col.type = Integer()


@pytest.fixture
async def db():
    """每个测试独立的 SQLite 内存库异步会话"""
    _sqlite_compatible_metadata()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,  # 内存库共享单连接,保证同库可见
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest.fixture(autouse=True)
async def _no_redis_writes(monkeypatch):
    """测试环境不写真实 Redis:写操作(会话/黑名单/验证码/库存)全局打桩为 no-op。
    读操作不在此打桩,由各测试自行打桩(如会话校验、黑名单)。
    """
    async def _noop(*args, **kwargs):
        pass
    monkeypatch.setattr("app.core.redis.redis_setex", _noop)
    monkeypatch.setattr("app.core.redis.redis_delete", _noop)
    monkeypatch.setattr("app.core.redis.redis_set", _noop)
    monkeypatch.setattr("app.core.redis.redis_decrby", _noop)
    monkeypatch.setattr("app.core.redis.redis_incrby", _noop)
    # order_service 以 from-import 方式持有引用,需在其命名空间打桩;返回 0=跳过(MySQL 兜底)
    async def _noop_deduct(*args, **kwargs):
        return 0
    monkeypatch.setattr("app.services.order_service.redis_stock_deduct", _noop_deduct)
    monkeypatch.setattr("app.services.order_service.redis_incrby", _noop)
    # coupon_service 同:限领标记返回 True(放行),Lua 返回 0(跳过,MySQL 兜底),读库存 None(用 DB 值)
    async def _noop_setnx(*args, **kwargs):
        return True
    monkeypatch.setattr("app.services.coupon_service.redis_setnx", _noop_setnx)
    monkeypatch.setattr("app.services.coupon_service.redis_stock_deduct", _noop_deduct)
    monkeypatch.setattr("app.services.coupon_service.redis_delete", _noop)
    monkeypatch.setattr("app.services.coupon_service.redis_setex", _noop)
    monkeypatch.setattr("app.services.coupon_service.redis_incrby", _noop)
    async def _noop_get(*args, **kwargs):
        return None
    monkeypatch.setattr("app.services.coupon_service.redis_get", _noop_get)
    # sign_service:位图操作打桩(默认未签到)
    async def _noop_zero(*args, **kwargs):
        return 0
    monkeypatch.setattr("app.services.sign_service.redis_getbit", _noop_zero)
    monkeypatch.setattr("app.services.sign_service.redis_setbit", _noop)
    monkeypatch.setattr("app.services.sign_service.redis_bitcount", _noop)
    monkeypatch.setattr("app.services.sign_service.redis_expire", _noop)
    monkeypatch.setattr("app.services.sign_service.redis_bitfield_unsigned", _noop_zero)
    async def _noop_exists(*args, **kwargs):
        return True  # 默认 key 已存在(不设 TTL)
    monkeypatch.setattr("app.services.sign_service.redis_exists", _noop_exists)
    # hot_service/order_service/dish/setmeal:ZSet 打桩(默认榜单空→走回填)
    async def _noop_empty(*args, **kwargs):
        return []
    monkeypatch.setattr("app.services.hot_service.redis_zrevrange_withscores", _noop_empty)
    monkeypatch.setattr("app.services.hot_service.redis_zadd", _noop)
    # 分布式锁:默认抢到锁,释放 noop
    async def _noop_lock(*args, **kwargs):
        return True
    monkeypatch.setattr("app.services.hot_service.redis_setnx", _noop_lock)
    monkeypatch.setattr("app.services.hot_service.redis_release_lock", _noop)
    monkeypatch.setattr("app.services.order_service.redis_zincrby", _noop)
    # 下单防重锁:默认拿到锁,释放 noop
    async def _noop_order_lock(*args, **kwargs):
        return True
    monkeypatch.setattr("app.services.order_service.redis_setnx", _noop_order_lock)
    monkeypatch.setattr("app.services.order_service.redis_release_lock", _noop)
    # dish/setmeal 删除路径的 Redis 清理(命名空间内 from-import)
    monkeypatch.setattr("app.services.dish_service.redis_delete", _noop)
    monkeypatch.setattr("app.services.dish_service.redis_zrem", _noop)
    monkeypatch.setattr("app.services.setmeal_service.redis_delete", _noop)
    monkeypatch.setattr("app.services.setmeal_service.redis_zrem", _noop)
