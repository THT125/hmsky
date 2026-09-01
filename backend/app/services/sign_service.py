"""签到有礼:Bitmap 按天签到,连续 5 天送 20 元无门槛优惠券。

Redis 设计:
- key: sign:{userId}:{yyyyMM}(每月一个 key,TTL 60 天自动清理)
- 位图:第 day-1 位 = 当天是否签到(SETBIT/GETBIT/BITCOUNT/BITFIELD)
- 连续天数:BITFIELD 一次取本月位图,Python 位运算从今天往前数连续的 1
- 奖励:连续满 5 天发一张"签到奖励20元券"(懒创建模板,发放幂等)
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.core.redis import (
    redis_bitcount,
    redis_bitfield_unsigned,
    redis_exists,
    redis_expire,
    redis_getbit,
    redis_setbit,
)
from app.models import Coupon, UserCoupon

logger = logging.getLogger("uvicorn.error")

REWARD_DAYS = 5  # 连续签到天数阈值
REWARD_NAME = "签到奖励20元券"
REWARD_VALID_DAYS = 30  # 奖励券领取后有效天数
_SIGN_TTL = 60 * 24 * 3600  # 每月 key 保留 60 天自动清理


def _sign_key(user_id: int, ym: str) -> str:
    return f"sign:{user_id}:{ym}"


async def _consecutive_days(key: str, today_index: int) -> int:
    """从今天往前数连续签到天数。
    BITFIELD GET u{n} 0 返回整数,第 i 天(offset i)落在位 (n-1-i):
    今天(最远位)在最低位(LSB),逐位往高位=往前一天。
    """
    bits = await redis_bitfield_unsigned(key, today_index + 1)
    count = 0
    for i in range(today_index, -1, -1):
        if (bits >> (today_index - i)) & 1:
            count += 1
        else:
            break
    return count


async def _get_reward_coupon(db: AsyncSession) -> Coupon:
    """签到奖励券模板(懒创建:20元无门槛,大总量,长期有效)"""
    coupon = (await db.execute(
        select(Coupon).where(Coupon.name == REWARD_NAME)
    )).scalar_one_or_none()
    if coupon is None:
        now = datetime.now()
        coupon = Coupon(
            name=REWARD_NAME, 
            type=1, 
            amount=20, 
            min_amount=0,
            total=999999, 
            stock=999999, 
            per_user_limit=1, 
            valid_days=REWARD_VALID_DAYS,
            start_time=now - timedelta(days=1), 
            end_time=now + timedelta(days=3650),
            status=1,
        )
        db.add(coupon)
        await db.commit()
        await db.refresh(coupon)
    return coupon


async def _grant_reward(db: AsyncSession, user_id: int) -> bool:
    """发放签到奖励券(幂等:已持有该券则不再发)"""
    coupon = await _get_reward_coupon(db)
    exists = (await db.scalar(select(func.count(UserCoupon.id)).where(
        UserCoupon.user_id == user_id, UserCoupon.coupon_id == coupon.id))) or 0
    if exists:
        return False  # 奖励已发过
    db.add(UserCoupon(user_id=user_id, coupon_id=coupon.id, status=0,
                      expire_time=datetime.now() + timedelta(days=REWARD_VALID_DAYS)))
    await db.commit()
    logger.info("用户 %s 连续签到 %d 天,发放签到奖励券", user_id, REWARD_DAYS)
    return True


async def sign(db: AsyncSession, user_id: int) -> dict:
    """签到:SETBIT 置位 + 连续天数统计 + 满 5 天发券"""
    now = datetime.now()
    key = _sign_key(user_id, now.strftime("%Y%m"))
    day_index = now.day - 1  # 位索引 0-based

    if await redis_getbit(key, day_index):
        raise BizException("今日已签到")

    first_sign = not await redis_exists(key)  # 首次创建才设 TTL,后续签到不续命(防止活跃用户 key 永不清理)
    await redis_setbit(key, day_index, 1)
    if first_sign:
        try:
            await redis_expire(key, _SIGN_TTL)  # EXPIRE 不动值,位图结构必须用它
        except Exception as e:
            logger.warning("签到 key TTL 设置降级: %s", e)

    consecutive = await _consecutive_days(key, day_index)
    reward = False
    if consecutive >= REWARD_DAYS:
        reward = await _grant_reward(db, user_id)
    return {"signedToday": True, "consecutiveDays": consecutive, "reward": reward}


async def sign_status(db: AsyncSession, user_id: int) -> dict:
    """签到状态:今日是否已签、连续天数、本月签到日历"""
    now = datetime.now()
    key = _sign_key(user_id, now.strftime("%Y%m"))
    day_index = now.day - 1
    today_signed = bool(await redis_getbit(key, day_index))
    consecutive = await _consecutive_days(key, day_index) if today_signed else 0
    bits = await redis_bitfield_unsigned(key, 31)
    # 位序:BITFIELD 整数中第 i 天(0-based)落在位 (30-i),第1天在最高位
    month_days = [1 if (bits >> (30 - i)) & 1 else 0 for i in range(now.day)]
    total = await redis_bitcount(key)
    return {
        "signedToday": today_signed,
        "consecutiveDays": consecutive,
        "monthDays": month_days,
        "totalDays": total,
    }
