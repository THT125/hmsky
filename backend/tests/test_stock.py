"""库存管理单元测试:下单预扣/库存不足拒绝/取消回补/回补幂等/不限量跳过"""
import pytest
from sqlalchemy import select

from app.core.exceptions import BizException
from app.models import AddressBook, Category, Dish, OrderDetail, Orders, Setmeal, ShopStatus, ShoppingCart
from app.schemas.business import OrdersSubmitIn
from app.services import cart_service, order_service


async def _seed(db, dish_stock=None, setmeal_stock=None):
    """种子:菜品分类/套餐分类 + 限量或不限量的菜品/套餐 + 地址 + 店铺营业"""
    db.add(Category(id=1, type=1, name="菜品分类", sort=1, status=1))
    db.add(Category(id=2, type=2, name="套餐分类", sort=1, status=1))
    db.add(Dish(id=1, name="测试菜", category_id=1, price=29.90, status=1, stock=dish_stock))
    db.add(Setmeal(id=1, name="测试套餐", category_id=2, price=66, status=1, stock=setmeal_stock))
    db.add(AddressBook(id=1, user_id=1, consignee="张三", phone="13911112222", detail="测试路1号", is_default=1))
    db.add(ShopStatus(id=1, status=1))  # 营业中
    await db.commit()


def _submit_in() -> OrdersSubmitIn:
    return OrdersSubmitIn(address_book_id=1, amount=100, delivery_status=1,
                          estimated_delivery_time=None, pack_amount=0, pay_method=1,
                          remark=None, tableware_number=1, tableware_status=0)


async def _add_dish_to_cart(db, number=1):
    for _ in range(number):
        await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor=None)


async def _add_setmeal_to_cart(db, number=1):
    for _ in range(number):
        await cart_service.add(db, user_id=1, dish_id=None, setmeal_id=1, dish_flavor=None)


async def _dish_stock(db):
    return (await db.execute(select(Dish.stock).where(Dish.id == 1))).scalar_one()


async def _setmeal_stock(db):
    return (await db.execute(select(Setmeal.stock).where(Setmeal.id == 1))).scalar_one()


# ===== 下单预扣 =====

async def test_submit_deducts_stock(db):
    """限量菜品下单扣库存"""
    await _seed(db, dish_stock=5)
    await _add_dish_to_cart(db, 2)
    order = await order_service.submit(db, 1, _submit_in())
    assert await _dish_stock(db) == 3
    # 订单明细记录数量
    details = (await db.execute(select(OrderDetail))).scalars().all()
    assert sum(d.number for d in details) == 2


async def test_submit_insufficient_stock_rejected(db):
    """库存不足:下单失败,库存不变"""
    await _seed(db, dish_stock=1)
    await _add_dish_to_cart(db, 2)
    with pytest.raises(BizException) as exc:
        await order_service.submit(db, 1, _submit_in())
    assert "库存不足" in str(exc.value)
    assert await _dish_stock(db) == 1  # 回滚,未扣减
    # 订单未创建
    assert (await db.scalar(select(Orders.id))) is None


async def test_unlimited_stock_skipped(db):
    """不限量(stock=NULL)下单不扣不减"""
    await _seed(db, dish_stock=None)
    await _add_dish_to_cart(db, 3)
    await order_service.submit(db, 1, _submit_in())
    assert await _dish_stock(db) is None


# ===== 取消回补 =====

async def test_cancel_restores_stock(db):
    """用户取消订单回补库存"""
    await _seed(db, dish_stock=5)
    await _add_dish_to_cart(db, 2)
    order = await order_service.submit(db, 1, _submit_in())
    assert await _dish_stock(db) == 3
    await order_service.user_cancel(db, 1, order["id"])
    assert await _dish_stock(db) == 5  # 回补


async def test_restore_idempotent(db):
    """回补幂等:重复回补只补一次(防超时任务与取消并发双回补)"""
    await _seed(db, dish_stock=5)
    await _add_dish_to_cart(db, 2)
    order = await order_service.submit(db, 1, _submit_in())
    order_obj = (await db.execute(select(Orders))).scalar_one()
    await order_service._restore_stock(db, order_obj)
    await order_service._restore_stock(db, order_obj)  # 第二次抢占失败
    assert await _dish_stock(db) == 5  # 只回补了一次


# ===== 套餐库存(独立) =====

async def test_setmeal_stock_deduct_and_restore(db):
    """套餐库存独立扣减/回补,不联动菜品"""
    await _seed(db, dish_stock=100, setmeal_stock=3)
    await _add_setmeal_to_cart(db, 1)
    order = await order_service.submit(db, 1, _submit_in())
    assert await _setmeal_stock(db) == 2
    assert await _dish_stock(db) == 100  # 菜品库存不受套餐消耗影响
    await order_service.user_cancel(db, 1, order["id"])
    assert await _setmeal_stock(db) == 3


async def test_setmeal_insufficient_stock_rejected(db):
    """套餐库存不足被拒"""
    await _seed(db, dish_stock=100, setmeal_stock=1)
    await _add_setmeal_to_cart(db, 2)
    with pytest.raises(BizException) as exc:
        await order_service.submit(db, 1, _submit_in())
    assert "库存不足" in str(exc.value)
    assert await _setmeal_stock(db) == 1


# ===== Redis Lua 抢购资格(第一步) =====

class _FakeRedis:
    def __init__(self, result):
        self._result = result

    async def eval(self, script, numkeys, key, amount):
        return self._result


async def _stub_redis_deduct(monkeypatch, result):
    from app.core import redis as redis_mod
    monkeypatch.setattr(redis_mod, "get_redis", lambda: _FakeRedis(result))


async def test_redis_deduct_ok(monkeypatch):
    """Lua 扣减成功返回剩余库存"""
    from app.core import redis as redis_mod
    await _stub_redis_deduct(monkeypatch, 4)
    assert await redis_mod.redis_stock_deduct("stock:dish:1", 1) == 4


async def test_redis_deduct_insufficient(monkeypatch):
    """Lua 返回 -1(库存不足,已回滚)"""
    from app.core import redis as redis_mod
    await _stub_redis_deduct(monkeypatch, -1)
    assert await redis_mod.redis_stock_deduct("stock:dish:1", 1) == -1


async def test_redis_deduct_skip_no_key(monkeypatch):
    """Lua 返回 0(无 key:不限量或未预热,交 MySQL 兜底)"""
    from app.core import redis as redis_mod
    await _stub_redis_deduct(monkeypatch, 0)
    assert await redis_mod.redis_stock_deduct("stock:dish:1", 1) == 0


async def test_redis_deduct_redis_down_fallback(monkeypatch):
    """Redis 不可用降级返回 0(放行,MySQL 兜底防超卖)"""
    from app.core import redis as redis_mod

    class _DownRedis:
        async def eval(self, script, numkeys, key, amount):
            raise ConnectionError("redis down")

    monkeypatch.setattr(redis_mod, "get_redis", lambda: _DownRedis())
    assert await redis_mod.redis_stock_deduct("stock:dish:1", 1) == 0


async def test_submit_redis_sold_out_rejected(db, monkeypatch):
    """Redis 已抢光(-1)直接拒绝,不碰 MySQL(挡并发的核心路径)"""
    from app.services import order_service as os_mod

    async def fake_deduct(key, amount):
        return -1

    monkeypatch.setattr(os_mod, "redis_stock_deduct", fake_deduct)
    await _seed(db, dish_stock=5)  # MySQL 有库存,但 Redis 已抢光
    await _add_dish_to_cart(db, 1)
    with pytest.raises(BizException) as exc:
        await order_service.submit(db, 1, _submit_in())
    assert "库存不足" in str(exc.value)
    assert await _dish_stock(db) == 5  # MySQL 未扣
