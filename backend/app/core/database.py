"""SQLAlchemy 2.0 异步数据库连接与 Session 管理"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import (
    DATABASE_URL,
    DB_ECHO,
    DB_MAX_OVERFLOW,
    DB_POOL_SIZE,
    DB_POOL_TIMEOUT,
)

engine = create_async_engine(
    DATABASE_URL,
    # 异步 engine 下 pool_pre_ping 会触发 aiomysql 同步桥接 ping → MissingGreenlet 坑,
    # 用 pool_recycle(1小时自动回收)保证连接不失效,等效防"断线连接"
    pool_recycle=3600,
    # 连接池(压测依据:默认 5+10 在高并发下成为瓶颈)
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    echo=DB_ECHO,  # 打印 SQL 日志开关(.env DB_ECHO=1)
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    autocommit=False, 
    autoflush=False, 
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI 依赖注入:每请求一个异步 Session"""
    async with AsyncSessionLocal() as db:
        yield db
