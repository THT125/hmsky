"""C端:热销排行榜(ZSet 实时销量)/user/hot"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.services import hot_service

router = APIRouter(prefix="/user/hot", tags=["C端-热销榜"])


@router.get("/list", dependencies=[Depends(get_current_user)])
async def list_hot(type: Optional[int] = Query(1, alias="type"),
                   top: Optional[int] = Query(10), db: AsyncSession = Depends(get_db)):
    """
    热销排行榜(实时销量,MySQL 权威 + Redis ZSet 加速)

    参数:
    - type (int): 1菜品 2套餐。
    - top (int): 取前 N 名,默认 10。

    返回:
    - Result: [{rank, id, name, price, image, description, sold 销量}]
    """
    return ok(await hot_service.list_hot(db, type or 1, top or 10))
