"""C端:分类查询 /user/category"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.services import category_service
from app.utils.orm import to_camel_dict

router = APIRouter(prefix="/user/category", tags=["C端-分类"])


@router.get("/list", dependencies=[Depends(get_current_user)])
async def list_by_type(type: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """
    条件查询分类

    参数:
    - type (int, 可选): 分类类型,1菜品分类 2套餐分类。
    - db (Session): 数据库会话。

    返回:
    - Result: 全部分类列表(含禁用的,前端根据 status 标记;禁用分类的商品不可下单)。
    """
    return ok([to_camel_dict(r) for r in await category_service.list_by_type(db, type)])
