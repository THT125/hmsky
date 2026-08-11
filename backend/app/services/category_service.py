"""分类管理(文案与原 CategoryServiceImpl 一致)"""
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.models import Category, Dish, Setmeal
from app.websocket.ws import push_menu_update


async def _notify_menu_change():
    """分类变更后推送菜单变更给用户端(type=5)"""
    await push_menu_update()


async def get_by_id(db: AsyncSession, cid: int) -> Optional[Category]:
    return await db.get(Category, cid)


async def add(db: AsyncSession, operator_id: int, type_: int, name: str, sort: int) -> Category:
    count = (await db.scalar(select(func.count(Category.id)).where(Category.name == name))) or 0
    if count > 0:
        raise BizException("分类名称已存在，请重新输入")
    cat = Category(type=type_, name=name, sort=sort, status=0)  # 新增默认禁用
    cat.create_user = operator_id  # 创建人(当前登录管理员)
    db.add(cat)
    await db.commit()
    await _notify_menu_change()
    return cat


async def update(db: AsyncSession, operator_id: int, cid: int, type_: int, name: str, sort: int) -> Category:
    cat = await get_by_id(db, cid)
    if cat is None:
        raise BizException("分类ID不存在")
    if cat.name != name:
        count = (await db.scalar(select(func.count(Category.id)).where(Category.name == name))) or 0
        if count > 0:
            raise BizException("分类名称已存在，请重新输入")
    cat.type = type_
    cat.name = name
    cat.sort = sort
    cat.update_user = operator_id  # 修改人(当前登录管理员)
    await db.commit()
    await _notify_menu_change()
    return cat


async def delete(db: AsyncSession, cid: int):
    cat = await get_by_id(db, cid)
    if cat is None:
        raise BizException("分类ID不存在")
    dish_count = (await db.scalar(select(func.count(Dish.id)).where(Dish.category_id == cid))) or 0
    setmeal_count = (await db.scalar(select(func.count(Setmeal.id)).where(Setmeal.category_id == cid))) or 0
    if dish_count > 0 or setmeal_count > 0:
        raise BizException("删除失败，当前分类下存在套餐或菜品，请检查")
    await db.delete(cat)
    await db.commit()
    await _notify_menu_change()


async def change_status(db: AsyncSession, operator_id: int, cid: int, status: int):
    cat = await get_by_id(db, cid)
    if cat is None:
        raise BizException("分类ID不存在")
    cat.status = status
    cat.update_user = operator_id  # 修改人(当前登录管理员)
    await db.commit()
    await _notify_menu_change()


async def page_query(db: AsyncSession, name: Optional[str], type_: Optional[int], page: int, page_size: int) -> tuple[int, list]:
    conds = []
    if name:
        conds.append(Category.name.like(f"%{name}%"))
    if type_ is not None:
        conds.append(Category.type == type_)
    total = (await db.scalar(select(func.count(Category.id)).where(*conds))) or 0
    result = await db.execute(
        select(Category)
        .where(*conds)
        .order_by(Category.sort.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return total, list(result.scalars().all())


async def list_by_type(db: AsyncSession, type_: Optional[int]) -> list:
    conds = []
    if type_ is not None:
        conds.append(Category.type == type_)
    result = await db.execute(select(Category).where(*conds).order_by(Category.sort.asc()))
    return list(result.scalars().all())
