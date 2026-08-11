"""菜品管理(文案与原 DishServiceImpl 一致,Redis 缓存与原项目一致)"""
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.core.redis import CACHE_DISHES, delete_key, hget_json, hset_json
from app.models import Category, Dish, DishFlavor, SetmealDish
from app.schemas.business import DishFlavorIn
from app.websocket.ws import push_menu_update


async def _invalidate_cache():
    """清除全部菜品缓存(等价于原项目 deleteAllDishCache)并推送菜单变更"""
    try:
        await delete_key(CACHE_DISHES)
    except Exception:
        pass  # Redis 不可用时静默
    await push_menu_update()  # 通知用户端刷新菜单


async def save(db: AsyncSession, operator_id: int, name: str, category_id: int, price, image: str,
               description: Optional[str], status: Optional[int], flavors: List[DishFlavorIn]):
    if (await db.scalar(select(func.count(Dish.id)).where(Dish.name == name))) > 0:
        raise BizException("菜品名称重复")
    if await db.get(Category, category_id) is None:
        raise BizException("分类ID不存在")
    dish = Dish(name=name, category_id=category_id, price=price, image=image,
                description=description, status=status if status is not None else 1)
    dish.create_user = operator_id  # 创建人(当前登录管理员)
    db.add(dish)
    await db.flush()
    for f in flavors or []:
        db.add(DishFlavor(dish_id=dish.id, name=f.name, value=f.value))
    await db.commit()
    await _invalidate_cache()
    return dish


async def update(
        db: AsyncSession,
        operator_id: int,
        dish_id: int,
        name: str,
        category_id: int,
        price, image: str,
        description: Optional[str],
        status: Optional[int],
        flavors: List[DishFlavorIn]
        ):
    dish = await db.get(Dish, dish_id)
    if dish is None:
        raise BizException("菜品ID不存在")
    if dish.name != name and (await db.scalar(select(func.count(Dish.id)).where(Dish.name == name))) > 0:
        raise BizException("菜品名称重复")
    dish.name = name
    dish.category_id = category_id
    dish.price = price
    dish.image = image
    dish.description = description
    if status is not None:
        dish.status = status
    dish.update_user = operator_id  # 修改人(当前登录管理员)
    # 口味先删后插
    await db.execute(delete(DishFlavor).where(DishFlavor.dish_id == dish_id))
    for f in flavors or []:
        db.add(DishFlavor(dish_id=dish_id, name=f.name, value=f.value))
    await db.commit()
    await _invalidate_cache()
    return dish


async def delete_by_ids(db: AsyncSession, ids: List[int]):
    # 起售中的菜品禁止删除
    selling = (await db.execute(select(Dish.id).where(Dish.id.in_(ids), Dish.status == 1))).scalars().all()
    if selling:
        raise BizException(f"删除失败，菜品ID为：{selling} 状态为起售中")
    # 关联套餐的菜品禁止删除
    linked = list({sd.dish_id for sd in (await db.execute(
        select(SetmealDish).where(SetmealDish.dish_id.in_(ids))
    )).scalars().all()})
    if linked:
        raise BizException(f"删除失败，菜品ID为：{linked} 存在关联套餐")
    await db.execute(delete(DishFlavor).where(DishFlavor.dish_id.in_(ids)))
    await db.execute(delete(Dish).where(Dish.id.in_(ids)))
    await db.commit()
    await _invalidate_cache()


async def get_by_id(db: AsyncSession, dish_id: int) -> Dish:
    dish = await db.get(Dish, dish_id)
    if dish is None:
        raise BizException("菜品ID不存在")
    return dish


async def change_status(db: AsyncSession, operator_id: int, dish_id: int, status: int):
    dish = await get_by_id(db, dish_id)
    if status == 0:
        linked = list((await db.execute(
            select(SetmealDish.dish_id).where(SetmealDish.dish_id == dish_id)
        )).scalars().all())
        if linked:
            raise BizException(f"修改状态失败，菜品ID为：{linked} 存在关联套餐")
    dish.status = status
    dish.update_user = operator_id  # 修改人(当前登录管理员)
    await db.commit()
    await _invalidate_cache()


async def page_query(db: AsyncSession, name: Optional[str], category_id: Optional[int],
                     status: Optional[int], page: int, page_size: int) -> tuple[int, list]:
    conds = []
    if name:
        conds.append(Dish.name.like(f"%{name}%"))
    if category_id is not None:
        conds.append(Dish.category_id == category_id)
    if status is not None:
        conds.append(Dish.status == status)
    total = (await db.scalar(select(func.count(Dish.id)).where(*conds))) or 0
    result = await db.execute(
        select(Dish)
        .where(*conds)
        .order_by(Dish.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return total, list(result.scalars().all())


async def list_by_category(db: AsyncSession, category_id: int, only_selling: bool = False) -> list:
    """按分类查询菜品(优先 Redis hash 缓存,miss 则查 DB 并回填)。
    与原项目 getDishVoListByCategoryId 缓存逻辑一致。
    """
    # 1. 尝试读缓存
    try:
        cached = await hget_json(CACHE_DISHES, str(category_id))
        if cached is not None:
            if only_selling:
                return [d for d in cached if d.get("status") == 1]
            return cached
    except Exception:
        pass  # Redis 不可用时降级查 DB

    # 2. 缓存未命中 → 查 DB
    conds = [Dish.category_id == category_id]
    if only_selling:
        conds.append(Dish.status == 1)
    dishes = (await db.execute(
        select(Dish).where(*conds).order_by(Dish.create_time.asc())
    )).scalars().all()
    result = [await build_vo(db, d) for d in dishes]

    # 3. 回填缓存(按原项目:缓存全量,包含停售的)
    try:
        all_dishes = (await db.execute(
            select(Dish).where(Dish.category_id == category_id).order_by(Dish.create_time.asc())
        )).scalars().all()
        all_vo = [await build_vo(db, d) for d in all_dishes]
        await hset_json(CACHE_DISHES, str(category_id), all_vo)
    except Exception:
        pass

    return result


async def get_flavors(db: AsyncSession, dish_id: int) -> list:
    rows = (await db.execute(
        select(DishFlavor).where(DishFlavor.dish_id == dish_id)
    )).scalars().all()
    return [{"id": f.id, "name": f.name, "value": f.value} for f in rows]


async def build_vo(db: AsyncSession, dish: Dish) -> dict:
    """组装 DishVO(含 categoryName、flavors)"""
    category_name = None
    if dish.category_id:
        cat = await db.get(Category, dish.category_id)
        category_name = cat.name if cat else None
    return {
        "id": dish.id,
        "name": dish.name,
        "categoryId": dish.category_id,
        "categoryName": category_name,
        "price": str(dish.price) if dish.price is not None else None,
        "image": dish.image,
        "description": dish.description,
        "status": dish.status,
        "createTime": dish.create_time,
        "updateTime": dish.update_time,
        "flavors": await get_flavors(db, dish.id),
    }
