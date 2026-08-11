"""C端:店铺营业状态 /user/shop(白名单,无需token)"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.services import shop_service

router = APIRouter(prefix="/user/shop", tags=["C端-店铺操作"])


@router.get("/status")
async def get_status(db: AsyncSession = Depends(get_db)):
    """
    获取营业状态

    参数:
    - db (Session): 数据库会话。

    返回:
    - Result: 1营业 0打烊。
    """
    return ok(await shop_service.get_status(db))
