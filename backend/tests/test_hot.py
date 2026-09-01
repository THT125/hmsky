"""热销榜单元测试:支付增销量/退款扣回/懒回填/榜单组装/删除清理"""
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import AddressBook, Category, Dish, OrderDetail, Orders, Setmeal, ShopStatus, ShoppingCart
from app.schemas.business import OrdersSubmitIn
from app.services import cart_service, dish_service, hot_service, order_service


async def _seed(db, dish_id=1, setmeal_id=1):
    db.add(Category(id=1, type=1, name="菜品分类", sort=1, status=1))
    db.add(Category(id=2, type=2, name="套餐分类", sort=1, status=1))
    db.add(Dish(id=dish_id, name="热销菜", category_id=1, price=29.90, status=1))
    db.add(Setmeal(id=setmeal_id, name="热销套餐", category_id=2, price=66, status=1))
    db.add(AddressBook(id=1, user_id=1, consignee="张三", phone="13911112222", detail="测试路1号", is_default=1))
    db.add(ShopStatus(id=1, status=1))
    await db.commit()


def _submit_in() -> OrdersSubmitIn:
    return OrdersSubmitIn(address_book_id=1, amount=100, delivery_status=1,
                          estimated_delivery_time=None, pack_amount=0, pay_method=1,
                          remark=None, tableware_number=1, tableware_status=0)


async def _submit_and_pay(db, number=2):
    for _ in range(number):
        await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor=None)
    order = await order_service.submit(db, 1, _submit_in())
    await order_service.payment(db, 1, order["orderNumber"])
    return order


async def test_payment_increments_hot_sales(db, monkeypatch):
    """支付成功:热销榜销量 +N(菜品按明细数量)"""
    from app.services import order_service as os_mod

    calls = []
    async def fake_zincrby(key, amount, member):
        calls.append((key, amount, member))

    monkeypatch.setattr(os_mod, "redis_zincrby", fake_zincrby)
    await _seed(db)
    await _submit_and_pay(db, number=2)
    assert (2, 1) in [(a, m) for _, a, m in calls]  # 数量2 × 1菜品
    assert all(k.startswith("hot:") for k, _, _ in calls)


async def test_paid_cancel_decrements(db, monkeypatch):
    """已支付订单取消:销量扣回(-N)"""
    from app.services import order_service as os_mod

    calls = []
    async def fake_zincrby(key, amount, member):
        calls.append((key, amount, member))

    monkeypatch.setattr(os_mod, "redis_zincrby", fake_zincrby)
    await _seed(db)
    order = await _submit_and_pay(db, number=2)
    await order_service.user_cancel(db, 1, order["id"])
    # 最后一次调用是扣回(-2)
    assert calls[-1][1] == -2


async def test_unpaid_cancel_no_decrement(db, monkeypatch):
    """未支付订单取消:不扣销量(从未计入)"""
    from app.services import order_service as os_mod

    calls = []
    async def fake_zincrby(key, amount, member):
        calls.append((key, amount, member))

    monkeypatch.setattr(os_mod, "redis_zincrby", fake_zincrby)
    await _seed(db)
    for _ in range(2):
        await cart_service.add(db, user_id=1, dish_id=1, setmeal_id=None, dish_flavor=None)
    order = await order_service.submit(db, 1, _submit_in())  # 未支付
    await order_service.user_cancel(db, 1, order["id"])
    assert calls == []  # 未支付:没有增也没有扣


async def test_list_backfill_and_rank(db, monkeypatch):
    """榜单 miss → 从 DB 回填,按销量倒序组装(含 rank/sold)"""
    from app.services import hot_service as hs

    await _seed(db)
    # 构造已支付订单明细:菜品1 销量3,菜品2 销量1
    db.add(Category(id=3, type=1, name="分类3", sort=1, status=1))
    db.add(Dish(id=2, name="次热销", category_id=3, price=10, status=1))
    o1 = Orders(user_id=2, address_book_id=1, number="H1", order_time=datetime.now(),
                amount=10, pay_method=1, pay_status=1, status=2, delivery_status=1)
    o2 = Orders(user_id=2, address_book_id=1, number="H2", order_time=datetime.now(),
                amount=10, pay_method=1, pay_status=1, status=2, delivery_status=1)
    db.add_all([o1, o2])
    await db.commit()
    db.add_all([
        OrderDetail(order_id=o1.id, name="热销菜", dish_id=1, number=3, amount=29.9),
        OrderDetail(order_id=o2.id, name="次热销", dish_id=2, number=1, amount=10),
    ])
    await db.commit()

    # 回填后读取(第一次 miss,第二次命中打桩返回回填数据)
    backfilled = {}
    async def fake_zadd(key, mapping):
        backfilled.update(mapping)

    async def fake_range(key, start, stop):
        # 第二次调用模拟回填后的 ZSet
        items = sorted(backfilled.items(), key=lambda kv: -kv[1])[:10]
        return [(k, float(v)) for k, v in items]

    calls = {"n": 0}
    async def fake_range_first(key, start, stop):
        calls["n"] += 1
        if calls["n"] == 1:
            return []
        return await fake_range(key, start, stop)

    monkeypatch.setattr(hs, "redis_zadd", fake_zadd)
    monkeypatch.setattr(hs, "redis_zrevrange_withscores", fake_range_first)

    result = await hot_service.list_hot(db, 1, top=10)
    assert len(result) == 2
    assert result[0]["rank"] == 1 and result[0]["sold"] == 3  # 热销菜排第一
    assert result[1]["rank"] == 2 and result[1]["sold"] == 1
    assert result[0]["name"] == "热销菜"


async def test_delete_cleans_hot_zset(db, monkeypatch):
    """删除商品:热销榜 ZREM 清理"""
    from app.services import dish_service as ds_mod
    from app.core.redis import HOT_DISHES_KEY

    removed = []
    async def fake_zrem(key, member):
        removed.append((key, member))

    monkeypatch.setattr(ds_mod, "redis_zrem", fake_zrem)
    await _seed(db)
    dish = (await db.execute(select(Dish).where(Dish.id == 1))).scalar_one()
    dish.status = 0  # 非起售才能删
    await db.commit()
    await dish_service.delete_by_ids(db, [1])
    assert (HOT_DISHES_KEY, 1) in removed


# ===== 分布式锁防重复重建 =====

async def test_lock_holder_backfills_and_releases(db, monkeypatch):
    """抢到锁:执行回填,最后安全释放锁"""
    from app.services import hot_service as hs

    await _seed(db)
    # 构造一笔已支付订单(销量数据源)
    o = Orders(user_id=2, address_book_id=1, number="HL1", order_time=datetime.now(),
               amount=10, pay_method=1, pay_status=1, status=2, delivery_status=1)
    db.add(o)
    await db.commit()
    db.add(OrderDetail(order_id=o.id, name="热销菜", dish_id=1, number=2, amount=29.9))
    await db.commit()

    calls = {"backfill": 0, "release": 0}
    async def fake_zadd(key, mapping):
        calls["backfill"] += 1
    async def fake_release(key, lock_id):
        calls["release"] += 1
    async def fake_lock(key, lock_id, ttl):
        return True  # 抢到锁

    async def fake_range(key, start, stop):
        return []  # 回填后仍空,走兜底

    monkeypatch.setattr(hs, "redis_zadd", fake_zadd)
    monkeypatch.setattr(hs, "redis_release_lock", fake_release)
    monkeypatch.setattr(hs, "redis_setnx", fake_lock)
    monkeypatch.setattr(hs, "redis_zrevrange_withscores", fake_range)

    await hot_service.list_hot(db, 1)
    assert calls["backfill"] >= 1
    assert calls["release"] == 1  # 锁已释放


async def test_lock_waiter_reads_after_holder(db, monkeypatch):
    """没抢到锁:等待后读到持锁者重建的数据(不重复回填)"""
    from app.services import hot_service as hs

    calls = {"backfill": 0}
    async def fake_zadd(key, mapping):
        calls["backfill"] += 1

    async def fake_lock(key, lock_id, ttl):
        return False  # 没抢到

    state = {"round": 0}
    async def fake_range(key, start, stop):
        state["round"] += 1
        if state["round"] >= 2:  # 持锁者重建完成
            return [(1, 3.0)]
        return []

    monkeypatch.setattr(hs, "redis_zadd", fake_zadd)
    monkeypatch.setattr(hs, "redis_setnx", fake_lock)
    monkeypatch.setattr(hs, "redis_zrevrange_withscores", fake_range)

    await _seed(db)
    result = await hot_service.list_hot(db, 1)
    assert calls["backfill"] == 0  # 等待者不重复回填
    assert result and result[0]["sold"] == 3  # 读到持锁者重建的数据


async def test_release_lock_uses_lua(db, monkeypatch):
    """redis_release_lock 通过 Lua 校验 value 再删除"""
    from app.core import redis as redis_mod

    evaled = []
    class _Fake:
        async def eval(self, script, numkeys, key, lock_id):
            evaled.append((script, key, lock_id))
    monkeypatch.setattr(redis_mod, "get_redis", lambda: _Fake())
    await redis_mod.redis_release_lock("lock:hot:dishes", "abc123")
    assert len(evaled) == 1
    assert "GET" in evaled[0][0] and "DEL" in evaled[0][0]  # Lua 含校验+删除
    assert evaled[0][1] == "lock:hot:dishes" and evaled[0][2] == "abc123"
