"""购物车单元测试:口味归一化(空字符串与 None 等价)"""
from sqlalchemy import select

from app.models import Category, Dish, ShoppingCart
from app.services import cart_service


async def _seed_dish(db, category_id=1):
    db.add(Category(id=category_id, type=1, name=f"分类{category_id}", sort=1, status=1))
    dish = Dish(id=1, name="测试菜", category_id=category_id, price=29.90, status=1)
    db.add(dish)
    await db.commit()
    return dish


async def test_add_with_empty_flavor_stores_null(db):
    """前端传空字符串口味,数据库应存 NULL(归一化)"""
    await _seed_dish(db)
    await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor="")
    row = (await db.execute(select(ShoppingCart))).scalars().first()
    assert row.dish_flavor is None


async def test_sub_with_null_matches_empty_flavor_added(db):
    """加购存空字符串后,减购传 None 能匹配到(修复前的 bug 场景)"""
    await _seed_dish(db)
    await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor="")
    # 减购传 None(前端 item.dishFlavor || null)
    await cart_service.sub(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor=None)
    assert len((await db.execute(select(ShoppingCart))).scalars().all()) == 0


async def test_add_accumulates_same_dish(db):
    """同用户同菜品重复加购数量累加"""
    await _seed_dish(db)
    await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor=None)
    await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor=None)
    row = (await db.execute(select(ShoppingCart))).scalars().first()
    assert row.number == 2


async def test_add_disabled_category_rejected(db):
    """禁用分类的商品不可加购"""
    db.add(Category(id=1, type=1, name="已禁用", sort=1, status=0))  # 禁用分类
    db.add(Dish(id=1, name="测试菜", category_id=1, price=29.90, status=1))
    await db.commit()
    from app.core.exceptions import BizException
    try:
        await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor=None)
        assert False, "应抛出分类禁用异常"
    except BizException as e:
        assert "禁用" in str(e)


async def test_add_invalid_params(db):
    """两个 id 同时为空/非空抛参数错误"""
    await _seed_dish(db)
    from app.core.exceptions import BizException
    try:
        await cart_service.add(db, user_id=1, dish_id=None, setmeal_id=None, dish_flavor=None)
        assert False, "应抛出参数错误"
    except BizException as e:
        assert "参数错误" in str(e)
