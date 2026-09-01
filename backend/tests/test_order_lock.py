"""下单防重复提交:分布式锁(锁粒度按用户)"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import BizException
from app.models import AddressBook, Category, Dish, Orders, ShopStatus, ShoppingCart
from app.schemas.business import OrdersSubmitIn
from app.services import cart_service, order_service


async def _seed(db):
    db.add(Category(id=1, type=1, name="菜品分类", sort=1, status=1))
    db.add(Dish(id=1, name="测试菜", category_id=1, price=29.90, status=1))
    db.add(AddressBook(id=1, user_id=1, consignee="张三", phone="13911112222", detail="测试路1号", is_default=1))
    db.add(ShopStatus(id=1, status=1))
    await db.commit()


def _submit_in() -> OrdersSubmitIn:
    return OrdersSubmitIn(address_book_id=1, amount=100, delivery_status=1,
                          estimated_delivery_time=None, pack_amount=0, pay_method=1,
                          remark=None, tableware_number=1, tableware_status=0)


async def _add_cart(db, n=1):
    for _ in range(n):
        await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor=None)


async def test_submit_lock_rejected(db, monkeypatch):
    """同用户并发提交:拿不到锁 → 拒绝(防重复下单)"""
    from app.services import order_service as os_mod

    async def fake_lock(key, lock_id, ttl):
        assert key == "lock:order:1"  # 锁粒度按用户
        return False  # 已有人在提交

    monkeypatch.setattr(os_mod, "redis_setnx", fake_lock)
    await _seed(db)
    await _add_cart(db)
    with pytest.raises(BizException) as exc:
        await order_service.submit(db, 1, _submit_in())
    assert "频繁" in str(exc.value)
    # 未创建订单
    assert (await db.scalar(select(Orders.id))) is None


async def test_submit_lock_released(db, monkeypatch):
    """正常下单:拿锁 → 下单成功 → 释放锁"""
    from app.services import order_service as os_mod

    calls = []
    async def fake_lock(key, lock_id, ttl):
        calls.append(("lock", key, lock_id))
        return True
    async def fake_release(key, lock_id):
        calls.append(("release", key, lock_id))

    monkeypatch.setattr(os_mod, "redis_setnx", fake_lock)
    monkeypatch.setattr(os_mod, "redis_release_lock", fake_release)
    await _seed(db)
    await _add_cart(db)
    order = await order_service.submit(db, 1, _submit_in())
    assert order["id"] is not None
    assert calls[0][0] == "lock" and calls[0][1] == "lock:order:1"
    assert calls[-1][0] == "release" and calls[-1][1] == "lock:order:1"  # finally 释放


async def test_submit_lock_fallback(db, monkeypatch):
    """Redis 异常:锁降级放行,业务不阻塞"""
    from app.services import order_service as os_mod

    async def fake_lock(key, lock_id, ttl):
        raise ConnectionError("redis down")

    monkeypatch.setattr(os_mod, "redis_setnx", fake_lock)
    await _seed(db)
    await _add_cart(db)
    order = await order_service.submit(db, 1, _submit_in())  # 不抛异常,下单成功
    assert order["id"] is not None
