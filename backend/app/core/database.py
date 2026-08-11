"""SQLAlchemy 2.0 异步数据库连接与 Session 管理"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import DATABASE_URL, DB_ECHO

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
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
