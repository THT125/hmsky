"""套餐管理(文案与原 SetMealServiceImpl 一致,Redis 缓存与原项目一致)"""
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.core.redis import CACHE_SETMEALS, delete_key, hget_json, hset_json
from app.models import Category, Dish, Setmeal, SetmealDish
from app.schemas.business import SetmealDishIn
from app.websocket.ws import push_menu_update


async def _invalidate_cache():
    """清除全部套餐缓存(等价于原项目 deleteAllSetMealCache)并推送菜单变更"""
    try:
        await delete_key(CACHE_SETMEALS)
    except Exception:
        pass
    await push_menu_update()  # 通知用户端刷新菜单


async def _check_dishes_exist_and_selling(db: AsyncSession, setmeal_dishes: List[SetmealDishIn]):
    dish_ids = list({sd.dish_id for sd in setmeal_dishes})
    selling_ids = list((await db.execute(
        select(Dish.id).where(Dish.id.in_(dish_ids), Dish.status == 1)
    )).scalars().all())
    if len(selling_ids) != len(dish_ids):
        missing = [did for did in dish_ids if did not in selling_ids]
        raise BizException(f"菜品ID: {missing} 已停售或者不存在")


async def save(db: AsyncSession, operator_id: int, category_id: int, name: str, price: Decimal, image: str,
               description: Optional[str], status: Optional[int], setmeal_dishes: List[SetmealDishIn]):
    if await db.get(Category, category_id) is None:
        raise BizException("分类ID不存在")
    if (await db.scalar(select(func.count(Setmeal.id)).where(Setmeal.name == name)) or 0) != 0:
        raise BizException("套餐名称重复")
    await _check_dishes_exist_and_selling(db, setmeal_dishes)

    setmeal = Setmeal(category_id=category_id, name=name, price=price, image=image,
                      description=description, status=status if status is not None else 1)
    setmeal.create_user = operator_id  # 创建人(当前登录管理员)
    db.add(setmeal)
    await db.flush()
    for sd in setmeal_dishes:
        db.add(SetmealDish(setmeal_id=setmeal.id, dish_id=sd.dish_id,
                           name=sd.name, price=sd.price, copies=sd.copies))
    await db.commit()
    await _invalidate_cache()
    return setmeal


async def update(db: AsyncSession, operator_id: int, setmeal_id: int, category_id: int, name: str, price: Decimal, image: str,
                 description: Optional[str], status: Optional[int], setmeal_dishes: List[SetmealDishIn]):
    old = await get_by_id(db, setmeal_id)
    if old.name != name and (await db.scalar(select(func.count(Setmeal.id)).where(Setmeal.name == name)) or 0) != 0:
        raise BizException("套餐名称重复")
    await _check_dishes_exist_and_selling(db, setmeal_dishes)

    old.category_id = category_id
    old.name = name
    old.price = price
    old.image = image
    old.description = description
    if status is not None:
        old.status = status
    old.update_user = operator_id  # 修改人(当前登录管理员)
    # 套餐菜品先删后插
    await db.execute(delete(SetmealDish).where(SetmealDish.setmeal_id == setmeal_id))
    for sd in setmeal_dishes:
        db.add(SetmealDish(setmeal_id=setmeal_id, dish_id=sd.dish_id,
                           name=sd.name, price=sd.price, copies=sd.copies))
    await db.commit()
    await _invalidate_cache()
    return old


async def delete_by_ids(db: AsyncSession, ids: List[int]):
    """起售中的套餐静默跳过,仅删除非起售套餐及其关联菜品(与原实现一致)"""
    not_selling = list((await db.execute(
        select(Setmeal.id).where(Setmeal.id.in_(ids), Setmeal.status != 1)
    )).scalars().all())
    if not not_selling:
        return
    await db.execute(delete(SetmealDish).where(SetmealDish.setmeal_id.in_(not_selling)))
    await db.execute(delete(Setmeal).where(Setmeal.id.in_(not_selling)))
    await db.commit()
    await _invalidate_cache()


async def get_by_id(db: AsyncSession, setmeal_id: int) -> Setmeal:
    s = await db.get(Setmeal, setmeal_id)
    if s is None:
        raise BizException("套餐ID不存在")
    return s


async def change_status(db: AsyncSession, operator_id: int, setmeal_id: int, status: int):
    s = await get_by_id(db, setmeal_id)
    s.status = status
    s.update_user = operator_id  # 修改人(当前登录管理员)
    await db.commit()
    await _invalidate_cache()


async def page_query(db: AsyncSession, name: Optional[str], category_id: Optional[int],
                     status: Optional[int], page: int, page_size: int) -> tuple[int, list]:
    conds = []
    if name:
        conds.append(Setmeal.name.like(f"%{name}%"))
    if category_id is not None:
        conds.append(Setmeal.category_id == category_id)
    if status is not None:
        conds.append(Setmeal.status == status)
    total = (await db.scalar(select(func.count(Setmeal.id)).where(*conds))) or 0
    result = await db.execute(
        select(Setmeal)
        .where(*conds)
        .order_by(Setmeal.create_time.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return total, list(result.scalars().all())


async def list_by_category(db: AsyncSession, category_id: int, only_selling: bool = False) -> list:
    """按分类查询套餐(优先 Redis hash 缓存,与原项目 getSetMealListByCategoryId 缓存逻辑一致)"""
    try:
        cached = await hget_json(CACHE_SETMEALS, str(category_id))
        if cached is not None:
            if only_selling:
                return [s for s in cached if s.get("status") == 1]
            return cached
    except Exception:
        pass

    conds = [Setmeal.category_id == category_id]
    if only_selling:
        conds.append(Setmeal.status == 1)
    setmeals = (await db.execute(select(Setmeal).where(*conds))).scalars().all()
    result = [await build_vo(db, s) for s in setmeals]

    # 回填缓存(全量,含停售)
    try:
        all_setmeals = (await db.execute(
            select(Setmeal).where(Setmeal.category_id == category_id)
        )).scalars().all()
        all_vo = [await build_vo(db, s) for s in all_setmeals]
        await hset_json(CACHE_SETMEALS, str(category_id), all_vo)
    except Exception:
        pass

    return result


async def get_setmeal_dishes(db: AsyncSession, setmeal_id: int) -> list:
    rows = (await db.execute(
        select(SetmealDish).where(SetmealDish.setmeal_id == setmeal_id)
    )).scalars().all()
    return [{"id": sd.id, "setmealId": sd.setmeal_id, "dishId": sd.dish_id,
             "name": sd.name, "price": str(sd.price) if sd.price is not None else None,
             "copies": sd.copies} for sd in rows]


async def build_vo(db: AsyncSession, setmeal: Setmeal) -> dict:
    category_name = None
    if setmeal.category_id:
        cat = await db.get(Category, setmeal.category_id)
        category_name = cat.name if cat else None
    return {
        "id": setmeal.id,
        "categoryId": setmeal.category_id,
        "categoryName": category_name,
        "name": setmeal.name,
        "price": str(setmeal.price) if setmeal.price is not None else None,
        "status": setmeal.status,
        "description": setmeal.description,
        "image": setmeal.image,
        "createTime": setmeal.create_time,
        "updateTime": setmeal.update_time,
        "setmealDishes": await get_setmeal_dishes(db, setmeal.id),
    }


async def get_dishes_by_setmeal(db: AsyncSession, setmeal_id: int) -> list:
    """用户端:根据套餐id查询包含的菜品 DishItemVO"""
    rows = (await db.execute(
        select(SetmealDish).where(SetmealDish.setmeal_id == setmeal_id)
    )).scalars().all()
    if not rows:
        raise BizException("当前套餐异常，菜品为空...")
    items = []
    for sd in rows:
        dish = await db.get(Dish, sd.dish_id)
        if dish:
            items.append({
                "copies": sd.copies,
                "description": dish.description,
                "image": dish.image,
                "name": dish.name,
            })
    return items
