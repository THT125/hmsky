"""C端:套餐浏览 /user/setmeal"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.services import setmeal_service

router = APIRouter(prefix="/user/setmeal", tags=["C端-套餐浏览"])


@router.get("/list", dependencies=[Depends(get_current_user)])
async def list_by_category(categoryId: int = Query(..., alias="categoryId"),
                           db: AsyncSession = Depends(get_db)):
    """
    根据分类id查询套餐

    参数:
    - categoryId (int): 套餐分类id。
    - db (Session): 数据库会话。

    返回:
    - Result: 起售套餐列表。
    """
    # list_by_category 内部已 build_vo + Redis 缓存
    return ok(await setmeal_service.list_by_category(db, categoryId, only_selling=True))


@router.get("/dish/{setmeal_id}", dependencies=[Depends(get_current_user)])
async def get_dishes(setmeal_id: int, db: AsyncSession = Depends(get_db)):
    """
    根据套餐id查询包含的菜品

    参数:
    - setmeal_id (int): 套餐id。
    - db (Session): 数据库会话。

    返回:
    - Result: 菜品列表,每项含 copies 份数、description 描述、image 图片、name 名称。
    """
    return ok(await setmeal_service.get_dishes_by_setmeal(db, setmeal_id))
