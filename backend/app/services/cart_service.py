"""购物车(文案与原 ShoppingCartServiceImpl 一致)"""
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.models import Category, Dish, Setmeal, ShoppingCart


async def _get_cart_item(db: AsyncSession, user_id: int, dish_id: Optional[int],
                         setmeal_id: Optional[int], dish_flavor: Optional[str]) -> Optional[ShoppingCart]:
    result = await db.execute(
        select(ShoppingCart).where(
            ShoppingCart.user_id == user_id,
            ShoppingCart.dish_id == dish_id,
            ShoppingCart.setmeal_id == setmeal_id,
            ShoppingCart.dish_flavor == dish_flavor,
        )
    )
    return result.scalar_one_or_none()


async def _check_sellable(db: AsyncSession, dish_id: Optional[int], setmeal_id: Optional[int]):
    """校验商品所属分类是否启用(禁用分类的商品不可加入购物车)"""
    if dish_id is not None:
        dish = await db.get(Dish, dish_id)
        if dish is not None:
            cat = await db.get(Category, dish.category_id)
            if cat is not None and cat.status != 1:
                raise BizException(f"分类已禁用:{cat.name},该分类商品无法购买")
    else:
        setmeal = await db.get(Setmeal, setmeal_id)
        if setmeal is not None:
            cat = await db.get(Category, setmeal.category_id)
            if cat is not None and cat.status != 1:
                raise BizException(f"分类已禁用:{cat.name},该分类商品无法购买")


async def add(db: AsyncSession, user_id: int, dish_id: Optional[int], setmeal_id: Optional[int], dish_flavor: Optional[str]):
    if (dish_id is None and setmeal_id is None) or (dish_id is not None and setmeal_id is not None):
        raise BizException("参数错误，别乱搞~")
    # 归一化:空字符串与 None 统一存 NULL,保证 add/sub 查询一致
    dish_flavor = dish_flavor or None
    # 禁用分类的商品不可加购
    await _check_sellable(db, dish_id, setmeal_id)

    item = await _get_cart_item(db, user_id, dish_id, setmeal_id, dish_flavor)
    if item is not None:
        item.number += 1
        await db.commit()
        return item

    # 首次添加:根据菜品/套餐组装购物车项
    if dish_id is not None:
        dish = await db.get(Dish, dish_id)
        if dish is None:
            raise BizException(f"菜品id不存在：{dish_id}")
        item = ShoppingCart(
            dish_id=dish.id, image=dish.image, name=dish.name,
            dish_flavor=dish_flavor, amount=dish.price,
        )
    else:
        setmeal = await db.get(Setmeal, setmeal_id)
        if setmeal is None:
            raise BizException(f"套餐ID不存在：{setmeal_id}")
        item = ShoppingCart(
            setmeal_id=setmeal.id, image=setmeal.image, name=setmeal.name, amount=setmeal.price,
        )
    item.number = 1
    item.user_id = user_id
    # create_time 由数据库 server_default 自动填充(CURRENT_TIMESTAMP)
    db.add(item)
    await db.commit()
    return item


async def sub(db: AsyncSession, user_id: int, dish_id: Optional[int], setmeal_id: Optional[int], dish_flavor: Optional[str]):
    if (dish_id is None and setmeal_id is None) or (dish_id is not None and setmeal_id is not None):
        raise BizException("必须指定菜品ID或套餐ID，二者只能传一个")
    # 归一化:空字符串与 None 统一(NULL)
    dish_flavor = dish_flavor or None
    item = await _get_cart_item(db, user_id, dish_id, setmeal_id, dish_flavor)
    if item is None:
        if dish_id is not None:
            raise BizException(f"没有找到对应的菜品ID：{dish_id}")
        raise BizException(f"没有找到对应的套餐ID：{setmeal_id}")
    if item.number == 1:
        await db.delete(item)
    else:
        item.number -= 1
    await db.commit()


async def list_items(db: AsyncSession, user_id: int) -> list:
    result = await db.execute(
        select(ShoppingCart)
        .where(ShoppingCart.user_id == user_id)
        .order_by(ShoppingCart.create_time.asc())
    )
    return list(result.scalars().all())


async def clean(db: AsyncSession, user_id: int):
    await db.execute(delete(ShoppingCart).where(ShoppingCart.user_id == user_id))
    await db.commit()
