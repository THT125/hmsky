"""C端:菜品浏览 /user/dish"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.services import dish_service

router = APIRouter(prefix="/user/dish", tags=["C端-菜品浏览"])


@router.get("/list", dependencies=[Depends(get_current_user)])
async def list_by_category(categoryId: int = Query(..., alias="categoryId"),
                           db: AsyncSession = Depends(get_db)):
    """
    根据分类id查询菜品

    参数:
    - categoryId (int): 菜品分类id。
    - db (Session): 数据库会话。

    返回:
    - Result: 起售菜品列表(含口味)。
    """
    # 用户端仅返回起售菜品(list_by_category 内部已 build_vo + Redis 缓存)
    return ok(await dish_service.list_by_category(db, categoryId, only_selling=True))
