"""套餐管理(文案与原 SetMealServiceImpl 一致,Redis 缓存与原项目一致)"""
import logging
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException

logger = logging.getLogger("uvicorn.error")
from app.core.redis import (
    CACHE_SETMEALS,
    HOT_SETMEALS_KEY,
    STOCK_SETMEAL_PREFIX,
    delete_key,
    hget_json,
    hset_json,
    redis_delete,
    redis_get,
    redis_set,
    redis_zrem,
)
from app.models import Category, Dish, Setmeal, SetmealDish
from app.schemas.business import SetmealDishIn
from app.websocket.ws import push_menu_update


async def _invalidate_cache():
    """清除全部套餐缓存(等价于原项目 deleteAllSetMealCache)并推送菜单变更"""
    try:
        await delete_key(CACHE_SETMEALS)
    except Exception as e:
        logger.warning("清除套餐缓存降级(Redis不可用): %s", e)
    await push_menu_update()  # 通知用户端刷新菜单


async def sync_stock_key(setmeal_id: int, stock: Optional[int]):
    """同步套餐库存到 Redis(NULL=不限量,删除 key)"""
    try:
        if stock is None:
            await redis_delete(f"{STOCK_SETMEAL_PREFIX}{setmeal_id}")
        else:
            await redis_set(f"{STOCK_SETMEAL_PREFIX}{setmeal_id}", str(stock))
    except Exception as e:
        logger.warning("同步套餐库存到Redis降级(MySQL为权威): %s", e)


async def _attach_stock(db: AsyncSession, vo: dict) -> dict:
    """把实时库存合并进 VO:优先 Redis key,miss 以 MySQL 为准刷新"""
    try:
        cached = await redis_get(f"{STOCK_SETMEAL_PREFIX}{vo['id']}")
        if cached is not None:
            vo["stock"] = int(cached)
        else:
            setmeal = await db.get(Setmeal, vo["id"])
            if setmeal is not None:
                vo["stock"] = setmeal.stock
                if setmeal.stock is not None:
                    await redis_set(f"{STOCK_SETMEAL_PREFIX}{vo['id']}", str(setmeal.stock))
    except Exception as e:
        logger.warning("合并套餐实时库存降级(保留MySQL值): %s", e)
    return vo


async def _check_dishes_exist_and_selling(db: AsyncSession, setmeal_dishes: List[SetmealDishIn]):
    dish_ids = list({sd.dish_id for sd in setmeal_dishes})
    selling_ids = list((await db.execute(
        select(Dish.id).where(Dish.id.in_(dish_ids), Dish.status == 1)
    )).scalars().all())
    if len(selling_ids) != len(dish_ids):
        missing = [did for did in dish_ids if did not in selling_ids]
        raise BizException(f"菜品ID: {missing} 已停售或者不存在")


async def save(db: AsyncSession, operator_id: int, category_id: int, name: str, price: Decimal, image: str,
               description: Optional[str], status: Optional[int], setmeal_dishes: List[SetmealDishIn],
               stock: Optional[int] = None):
    if await db.get(Category, category_id) is None:
        raise BizException("分类ID不存在")
    if (await db.scalar(select(func.count(Setmeal.id)).where(Setmeal.name == name)) or 0) != 0:
        raise BizException("套餐名称重复")
    await _check_dishes_exist_and_selling(db, setmeal_dishes)

    setmeal = Setmeal(category_id=category_id, name=name, price=price, image=image,
                      description=description, status=status if status is not None else 1,
                      stock=stock)
    setmeal.create_user = operator_id  # 创建人(当前登录管理员)
    db.add(setmeal)
    await db.flush()
    for sd in setmeal_dishes:
        db.add(SetmealDish(setmeal_id=setmeal.id, dish_id=sd.dish_id,
                           name=sd.name, price=sd.price, copies=sd.copies))
    await db.commit()
    await sync_stock_key(setmeal.id, setmeal.stock)
    await _invalidate_cache()
    return setmeal


async def update(db: AsyncSession, operator_id: int, setmeal_id: int, category_id: int, name: str, price: Decimal, image: str,
                 description: Optional[str], status: Optional[int], setmeal_dishes: List[SetmealDishIn],
                 stock: Optional[int] = None):
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
    old.stock = stock  # 编辑保存=全量设置(NULL 表示改为不限量)
    old.update_user = operator_id  # 修改人(当前登录管理员)
    # 套餐菜品先删后插
    await db.execute(delete(SetmealDish).where(SetmealDish.setmeal_id == setmeal_id))
    for sd in setmeal_dishes:
        db.add(SetmealDish(setmeal_id=setmeal_id, dish_id=sd.dish_id,
                           name=sd.name, price=sd.price, copies=sd.copies))
    await db.commit()
    await sync_stock_key(setmeal_id, old.stock)
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
    for setmeald in not_selling:
        try:
            await redis_delete(f"{STOCK_SETMEAL_PREFIX}{setmeald}")
            await redis_zrem(HOT_SETMEALS_KEY, setmeald)  # 热销榜清理
        except Exception as e:
            logger.warning("删除套餐Redis key降级: %s", e)
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
            # 库存是高频变动数据,不在 VO 缓存中:命中后逐个合并实时库存
            merged = []
            for s in cached:
                if only_selling and s.get("status") != 1:
                    continue
                merged.append(await _attach_stock(db, s))
            return merged
    except Exception as e:
        logger.warning("读套餐缓存降级(查DB): %s", e)

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
    except Exception as e:
        logger.warning("回填套餐缓存降级: %s", e)

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
        "stock": setmeal.stock,
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
