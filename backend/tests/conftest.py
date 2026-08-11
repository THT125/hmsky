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
    """测试环境不写真实 Redis:写操作(会话/黑名单/验证码)全局打桩为 no-op。
    读操作不在此打桩,由各测试自行打桩(如会话校验、黑名单)。
    """
    async def _noop(*args, **kwargs):
        pass
    monkeypatch.setattr("app.core.redis.redis_setex", _noop)
    monkeypatch.setattr("app.core.redis.redis_delete", _noop)
