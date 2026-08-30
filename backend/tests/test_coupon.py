"""优惠券单元测试:模板校验/抢券/库存不足/一人限领/时间/唯一约束兜底/删除保护"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import BizException
from app.models import Coupon, UserCoupon
from app.schemas.business import CouponIn
from app.services import coupon_service

NOW = datetime.now()


def _coupon_in(**overrides):
    data = {
        "name": "测试满减券", "type": 1, "amount": 5, "min_amount": 20, "total": 100,
        "per_user_limit": 1,
        "start_time": (NOW - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": (NOW + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
        "status": 1,
    }
    data.update(overrides)
    return CouponIn(**data)


async def _seed_coupon(db, total=5, status=1, start=None, end=None):
    c = Coupon(name="种子券", type=1, amount=5, min_amount=20, total=total, stock=total,
               per_user_limit=1,
               start_time=start or (NOW - timedelta(hours=1)),
               end_time=end or (NOW + timedelta(hours=24)), status=status)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _stock(db, coupon_id):
    return (await db.execute(select(Coupon.stock).where(Coupon.id == coupon_id))).scalar_one()


# ===== 模板 CRUD 校验 =====

async def test_create_coupon_stock_equals_total(db):
    """新增券:剩余=总量,返回 dict(ORM 不出 service 层)"""
    c = await coupon_service.create(db, 1, _coupon_in())
    assert c["stock"] == c["total"] == 100


async def test_create_validation(db):
    """参数校验:面值/总量/限领/有效天数/时间"""
    with pytest.raises(BizException) as e:
        await coupon_service.create(db, 1, _coupon_in(amount=0))
    assert "面值" in str(e.value)
    with pytest.raises(BizException) as e:
        await coupon_service.create(db, 1, _coupon_in(total=0))
    assert "总量" in str(e.value)
    with pytest.raises(BizException) as e:
        await coupon_service.create(db, 1, _coupon_in(per_user_limit=0))
    assert "限领" in str(e.value)
    with pytest.raises(BizException) as e:
        await coupon_service.create(db, 1, _coupon_in(valid_days=0))
    assert "有效天数" in str(e.value)
    with pytest.raises(BizException) as e:
        await coupon_service.create(db, 1, _coupon_in(
            start_time=(NOW + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            end_time=NOW.strftime("%Y-%m-%d %H:%M:%S")))
    assert "结束时间" in str(e.value)


async def test_update_replenish_stock(db):
    """编辑补货:stock 可更新"""
    c = await coupon_service.create(db, 1, _coupon_in(total=10))
    dto = _coupon_in(name="测试满减券", total=10, stock=50)
    dto.id = c["id"]
    await coupon_service.update(db, 1, c["id"], dto)
    assert await _stock(db, c["id"]) == 50


async def test_delete_protected(db):
    """有用户领取的券禁止删除"""
    c = await _seed_coupon(db)
    db.add(UserCoupon(user_id=1, coupon_id=c.id, status=0))
    await db.commit()
    with pytest.raises(BizException) as e:
        await coupon_service.delete_by_ids(db, [c.id])
    assert "领取" in str(e.value)


async def test_delete_success(db):
    """无领取记录的券可删除(回归:sql_update 命名遮蔽修复)"""
    c = await _seed_coupon(db)
    await coupon_service.delete_by_ids(db, [c.id])
    assert (await db.get(Coupon, c.id)) is None


# ===== 抢券 =====

async def test_grab_success(db):
    """抢券成功:库存-1,持有记录插入,过期时间=领取+有效天数"""
    c = await _seed_coupon(db, total=5)
    result = await coupon_service.grab(db, 1, c.id)
    assert result["stock"] == 4
    assert await _stock(db, c.id) == 4
    uc = (await db.execute(select(UserCoupon).where(UserCoupon.user_id == 1))).scalars().all()
    assert len(uc) == 1 and uc[0].status == 0
    assert uc[0].expire_time is not None
    # 默认有效 7 天(容差秒级,避免毫秒截断)
    remaining = (uc[0].expire_time - datetime.now()).total_seconds()
    assert 7 * 86400 - 5 <= remaining <= 7 * 86400


async def test_grab_sold_out(db):
    """库存为0拒绝"""
    c = await _seed_coupon(db, total=0)
    with pytest.raises(BizException) as e:
        await coupon_service.grab(db, 1, c.id)
    assert "抢完" in str(e.value)


async def test_grab_not_started(db):
    """未开始拒绝"""
    c = await _seed_coupon(db, start=NOW + timedelta(hours=1))
    with pytest.raises(BizException) as e:
        await coupon_service.grab(db, 1, c.id)
    assert "未开始" in str(e.value)


async def test_grab_ended(db):
    """已结束拒绝"""
    c = await _seed_coupon(db, end=NOW - timedelta(hours=1))
    with pytest.raises(BizException) as e:
        await coupon_service.grab(db, 1, c.id)
    assert "已结束" in str(e.value)


async def test_grab_disabled(db):
    """停用券拒绝"""
    c = await _seed_coupon(db, status=0)
    with pytest.raises(BizException) as e:
        await coupon_service.grab(db, 1, c.id)
    assert "停用" in str(e.value)


async def test_grab_duplicate_rejected(db, monkeypatch):
    """一人限领:重复抢被拒(限领标记已存在)"""
    from app.services import coupon_service as cs

    async def fake_setnx(key, value, ttl):
        return False  # 已领取过

    monkeypatch.setattr(cs, "redis_setnx", fake_setnx)
    c = await _seed_coupon(db)
    with pytest.raises(BizException) as e:
        await coupon_service.grab(db, 1, c.id)
    assert "已领取" in str(e.value)
    assert await _stock(db, c.id) == 5  # 库存未扣


async def test_grab_lua_sold_out_rollback(db, monkeypatch):
    """Redis 已抢完(Lua -1):回滚限领标记(可再次尝试),MySQL 未扣"""
    from app.services import coupon_service as cs

    c = await _seed_coupon(db, total=5)
    deleted_keys = []
    async def fake_delete(key):
        deleted_keys.append(key)
    async def fake_deduct(key, amount):
        return -1  # Redis 已抢完
    monkeypatch.setattr(cs, "redis_delete", fake_delete)
    monkeypatch.setattr(cs, "redis_stock_deduct", fake_deduct)

    with pytest.raises(BizException) as e:
        await coupon_service.grab(db, 1, c.id)
    assert "抢完" in str(e.value)
    assert len(deleted_keys) == 1  # 限领标记已回滚
    assert await _stock(db, c.id) == 5  # MySQL 未扣


async def test_grab_unique_constraint_backup(db, monkeypatch):
    """唯一约束兜底:DB 已有领取记录(限领标记被 TTL 清理后重试) → 捕获 IntegrityError 转业务异常"""
    from app.services import coupon_service as cs

    async def fake_setnx(key, value, ttl):
        return True  # 限领标记放行(模拟 Redis 标记已过期)

    monkeypatch.setattr(cs, "redis_setnx", fake_setnx)
    c = await _seed_coupon(db, total=5)
    db.add(UserCoupon(user_id=1, coupon_id=c.id, status=0))  # DB 已有记录
    await db.commit()
    with pytest.raises(BizException) as e:
        await coupon_service.grab(db, 1, c.id)
    assert "已领取" in str(e.value)


# ===== 我的券 =====

async def test_my_coupons_expired(db):
    """我的券:未用且超过过期时间(领取+有效天数)的展示为已过期(2)"""
    c = await _seed_coupon(db)
    db.add(UserCoupon(user_id=1, coupon_id=c.id, status=0,
                      expire_time=NOW - timedelta(hours=1)))  # 已过期
    await db.commit()
    mine = await coupon_service.my_coupons(db, 1, None)
    assert len(mine) == 1
    assert mine[0]["status"] == 2  # 展示层计算过期


async def test_my_coupons_not_expired(db):
    """我的券:未过过期时间的保持未用(0)"""
    c = await _seed_coupon(db)
    db.add(UserCoupon(user_id=1, coupon_id=c.id, status=0,
                      expire_time=NOW + timedelta(days=3)))  # 未过期
    await db.commit()
    mine = await coupon_service.my_coupons(db, 1, None)
    assert mine[0]["status"] == 0


async def test_my_coupons_filter(db):
    """我的券:按状态过滤"""
    c1 = await _seed_coupon(db)
    db.add(UserCoupon(user_id=1, coupon_id=c1.id, status=0))
    await db.commit()
    mine = await coupon_service.my_coupons(db, 1, 0)
    assert len(mine) == 1
    assert await coupon_service.my_coupons(db, 1, 1) == []  # 已用为空
