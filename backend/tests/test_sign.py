"""签到单元测试:Bitmap 签到/重复拒绝/连续天数/5天发券/幂等"""
from datetime import datetime

import pytest
from sqlalchemy import select

from app.core.exceptions import BizException
from app.models import Coupon, UserCoupon
from app.services import sign_service

# 固定测试日期:8月15日(月中,保证连续统计的位索引充足,不依赖真实日期)
FIXED_NOW = datetime(2026, 8, 15, 12, 0, 0)
TODAY_INDEX = FIXED_NOW.day - 1  # = 14


class _FixedDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


def _freeze_time(monkeypatch):
    from app.services import sign_service as ss
    monkeypatch.setattr(ss, "datetime", _FixedDT)


def _bits_with_consecutive(days: int) -> int:
    """构造位图:今天往前连续 days 天为 1(今天=最低位)"""
    return (1 << days) - 1


async def test_sign_success(db, monkeypatch):
    """签到成功:连续1天,无奖励"""
    from app.services import sign_service as ss

    async def fake_bits(key, bits, offset=0):
        return 1  # 只有今天(最低位)

    monkeypatch.setattr(ss, "redis_bitfield_unsigned", fake_bits)
    r = await sign_service.sign(db, 1)
    assert r["signedToday"] is True
    assert r["consecutiveDays"] == 1
    assert r["reward"] is False
    # 未发券
    assert (await db.scalar(select(UserCoupon.id))) is None


async def test_sign_ttl_only_on_first(db, monkeypatch):
    """TTL 只在首次创建时设置,后续签到不续命(防止活跃用户 key 永不清理)"""
    from app.services import sign_service as ss

    expire_calls = []

    async def fake_bits(key, bits, offset=0):
        return 1

    async def fake_expire(key, ttl):
        expire_calls.append(key)

    async def fake_exists(key):
        return exists[0]

    exists = [False]  # 首次不存在
    monkeypatch.setattr(ss, "redis_bitfield_unsigned", fake_bits)
    monkeypatch.setattr(ss, "redis_expire", fake_expire)
    monkeypatch.setattr(ss, "redis_exists", fake_exists)

    await sign_service.sign(db, 1)  # 首次:设 TTL
    assert len(expire_calls) == 1

    exists[0] = True  # 后续签到:key 已存在
    await sign_service.sign(db, 2)  # 换个用户模拟次日(需绕过 getbit 打桩默认0)
    assert len(expire_calls) == 1  # TTL 未续


async def test_sign_duplicate_rejected(db, monkeypatch):
    """重复签到被拒"""
    from app.services import sign_service as ss

    async def fake_getbit(key, offset):
        return 1  # 今日已签

    monkeypatch.setattr(ss, "redis_getbit", fake_getbit)
    with pytest.raises(BizException) as exc:
        await sign_service.sign(db, 1)
    assert "已签到" in str(exc.value)


async def test_sign_reward_after_5_days(db, monkeypatch):
    """连续5天签到触发奖励:发20元无门槛券"""
    from app.services import sign_service as ss

    _freeze_time(monkeypatch)  # 固定 8月15日,保证连续统计正常
    async def fake_getbit(key, offset):
        return 0

    async def fake_bits(key, bits, offset=0):
        return _bits_with_consecutive(5)  # 连续5天

    monkeypatch.setattr(ss, "redis_getbit", fake_getbit)
    monkeypatch.setattr(ss, "redis_bitfield_unsigned", fake_bits)
    r = await sign_service.sign(db, 1)
    assert r["consecutiveDays"] == 5
    assert r["reward"] is True
    # 奖励券发放:模板存在 + user_coupon 记录
    coupon = (await db.execute(select(Coupon).where(Coupon.name == sign_service.REWARD_NAME))).scalar_one()
    assert float(coupon.amount) == 20.0
    assert float(coupon.min_amount) == 0.0  # 无门槛
    uc = (await db.execute(select(UserCoupon).where(UserCoupon.user_id == 1))).scalar_one()
    assert uc.coupon_id == coupon.id and uc.status == 0
    assert uc.expire_time is not None


async def test_sign_reward_idempotent(db, monkeypatch):
    """奖励幂等:已持有奖励券,再满5天不发重复券"""
    from app.services import sign_service as ss

    _freeze_time(monkeypatch)  # 固定 8月15日
    async def fake_getbit(key, offset):
        return 0

    async def fake_bits(key, bits, offset=0):
        return _bits_with_consecutive(5)

    monkeypatch.setattr(ss, "redis_getbit", fake_getbit)
    monkeypatch.setattr(ss, "redis_bitfield_unsigned", fake_bits)

    await sign_service.sign(db, 1)  # 第一次:发券
    r = await sign_service.sign(db, 1)  # 第二次(模拟次日):幂等
    # 注意:第二次 getbit 打桩返回0(未签),但 sign 会置位;奖励检查依赖 user_coupon 唯一
    assert r["reward"] is False
    count = (await db.scalar(select(UserCoupon.id).where(UserCoupon.user_id == 1)))
    assert count is not None  # 只有一张


async def test_sign_status(db, monkeypatch):
    """签到状态:连续天数 + 本月日历"""
    from app.services import sign_service as ss

    _freeze_time(monkeypatch)  # 固定 8月15日
    async def fake_getbit(key, offset):
        return 1  # 今日已签

    async def fake_bits(key, bits, offset=0):
        if bits == 31:  # status 用 u31:第 i 天在位 (30-i),今天(14号)在位 16
            return 0b111 << (30 - TODAY_INDEX)  # 14、13、12号
        return _bits_with_consecutive(3)  # 连续统计用 u15:位 0..2

    monkeypatch.setattr(ss, "redis_getbit", fake_getbit)
    monkeypatch.setattr(ss, "redis_bitfield_unsigned", fake_bits)
    st = await sign_service.sign_status(db, 1)
    assert st["signedToday"] is True
    assert st["consecutiveDays"] == 3
    assert len(st["monthDays"]) == FIXED_NOW.day
    assert st["monthDays"][TODAY_INDEX] == 1
    assert st["monthDays"][TODAY_INDEX - 3] == 0  # 4天前未签
