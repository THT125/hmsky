"""优惠券:券模板 CRUD + 抢券(Redis 当闸门三层防超发,MySQL 只接赢家)"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func, select, text
from sqlalchemy import update as sql_update  # 改名避免与模块级 update 服务函数冲突
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.core.redis import (
    COUPON_STOCK_PREFIX,
    COUPON_USER_PREFIX,
    redis_delete,
    redis_get,
    redis_incrby,
    redis_setex,
    redis_setnx,
    redis_stock_deduct,
)
from app.models import Coupon, UserCoupon

logger = logging.getLogger("uvicorn.error")


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        raise BizException("时间格式不正确(YYYY-MM-DD HH:mm:ss)")


def _validate(dto) -> None:
    """券模板参数校验(生产级:金额/总量/限领/时间)"""
    if not (dto.name or "").strip():
        raise BizException("券名称不能为空")
    if dto.type not in (1, 2):
        raise BizException("类型不正确(1满减 2折扣)")
    if dto.amount <= 0:
        raise BizException("面值必须大于0")
    if dto.min_amount < 0:
        raise BizException("使用门槛不能为负")
    if dto.total <= 0:
        raise BizException("发放总量必须大于0")
    if dto.per_user_limit < 1:
        raise BizException("每人限领必须≥1")
    if dto.valid_days < 1:
        raise BizException("有效天数必须≥1")
    if dto.start_time >= dto.end_time:
        raise BizException("结束时间必须晚于开始时间")


# ===== Redis 同步(写操作后维护;失败降级,MySQL 为权威) =====

async def _sync_stock_key(coupon_id: int, stock: int, end_time: datetime):
    """同步库存到 Redis,TTL=活动剩余时间(活动结束自动清理,不留僵尸 key)"""
    try:
        ttl = max(int((end_time - datetime.now()).total_seconds()), 60)
        await redis_setex(f"{COUPON_STOCK_PREFIX}{coupon_id}", ttl, str(stock))
    except Exception as e:
        logger.warning("同步优惠券库存到Redis降级: %s", e)


async def _redis_incr_stock(key: str, n: int):
    try:
        await redis_incrby(key, n)
    except Exception as e:
        logger.warning("Redis优惠券库存回补降级: %s", e)


# ===== 管理端:模板 CRUD =====

async def create(db: AsyncSession, operator_id: int, dto) -> Coupon:
    _validate(dto)
    exists = (await db.scalar(select(func.count(Coupon.id)).where(Coupon.name == dto.name))) or 0
    if exists:
        raise BizException("券名称重复")
    coupon = Coupon(
        name=dto.name.strip(), 
        type=dto.type, 
        amount=dto.amount,
        min_amount=dto.min_amount, 
        total=dto.total, stock=dto.total,  # 初始剩余=总量
        per_user_limit=dto.per_user_limit, 
        valid_days=dto.valid_days,
        start_time=_parse_dt(dto.start_time), 
        end_time=_parse_dt(dto.end_time),
        status=dto.status if dto.status is not None else 1,
        create_user=operator_id,
    )
    db.add(coupon)
    await db.commit()
    await _sync_stock_key(coupon.id, coupon.stock, coupon.end_time)  # 预热存量
    return _coupon_vo(coupon, coupon.stock)  # 返回 dict(ORM 不出 service 层,避免异步序列化触发 refresh)


async def update(db: AsyncSession, operator_id: int, coupon_id: int, dto) -> Coupon:
    coupon = await db.get(Coupon, coupon_id)
    if coupon is None:
        raise BizException("优惠券不存在")
    _validate(dto)
    if coupon.name != dto.name and (await db.scalar(
            select(func.count(Coupon.id)).where(Coupon.name == dto.name)) or 0):
        raise BizException("券名称重复")
    coupon.name = dto.name.strip()
    coupon.type = dto.type
    coupon.amount = dto.amount
    coupon.min_amount = dto.min_amount
    coupon.total = dto.total
    coupon.per_user_limit = dto.per_user_limit
    coupon.valid_days = dto.valid_days
    coupon.start_time = _parse_dt(dto.start_time)
    coupon.end_time = _parse_dt(dto.end_time)
    if dto.stock is not None:
        coupon.stock = dto.stock  # 编辑可补货(设置剩余量)
    coupon.update_user = operator_id
    await db.commit()
    await _sync_stock_key(coupon_id, coupon.stock, coupon.end_time)
    return _coupon_vo(coupon, coupon.stock)


async def change_status(db: AsyncSession, operator_id: int, coupon_id: int, status: int):
    coupon = await db.get(Coupon, coupon_id)
    if coupon is None:
        raise BizException("优惠券不存在")
    if status not in (0, 1):
        raise BizException("状态参数不正确")
    coupon.status = status
    coupon.update_user = operator_id
    await db.commit()


async def delete_by_ids(db: AsyncSession, ids: List[int]):
    """物理删除:已有用户领取的券禁止删除(有领取记录只能下架)"""
    claimed = (await db.scalar(
        select(func.count(UserCoupon.id)).where(UserCoupon.coupon_id.in_(ids)))) or 0
    if claimed:
        raise BizException("已有用户领取,不能删除(可下架停止发放)")
    await db.execute(sql_update(Coupon).where(Coupon.id.in_(ids)).values(status=0))  # 逻辑下架保底
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Coupon).where(Coupon.id.in_(ids)))
    await db.commit()
    for cid in ids:
        try:
            await redis_delete(f"{COUPON_STOCK_PREFIX}{cid}")
        except Exception as e:
            logger.warning("删除优惠券Redis key降级: %s", e)


async def page_query(db: AsyncSession, name: Optional[str], status: Optional[int],
                     page: int, page_size: int) -> tuple[int, list]:
    conds = []
    if name:
        conds.append(Coupon.name.like(f"%{name}%"))
    if status is not None:
        conds.append(Coupon.status == status)
    total = (await db.scalar(select(func.count(Coupon.id)).where(*conds))) or 0
    rows = (await db.execute(
        select(Coupon).where(*conds).order_by(Coupon.create_time.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return total, list(rows)


# ===== 用户端:抢券(核心) =====

def _coupon_vo(c: Coupon, stock: int) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "type": c.type,
        "amount": str(c.amount),
        "minAmount": str(c.min_amount),
        "total": c.total,
        "stock": stock,
        "perUserLimit": c.per_user_limit,
        "validDays": c.valid_days,
        "startTime": c.start_time,
        "endTime": c.end_time,
        "status": c.status,
    }


async def _real_stock(coupon_id: int, db_stock: int, end_time: datetime) -> int:
    """实时库存:优先 Redis key,miss 以 DB 为准并回填(TTL=活动剩余时间)"""
    try:
        cached = await redis_get(f"{COUPON_STOCK_PREFIX}{coupon_id}")
        if cached is not None:
            return int(cached)
        ttl = max(int((end_time - datetime.now()).total_seconds()), 60)
        await redis_setex(f"{COUPON_STOCK_PREFIX}{coupon_id}", ttl, str(db_stock))
    except Exception as e:
        logger.warning("读优惠券库存降级: %s", e)
    return db_stock


async def list_for_user(db: AsyncSession, user_id: int) -> list:
    """领券中心列表:上架券 + 实时库存 + 用户领取状态 + 可领状态"""
    coupons = (await db.execute(
        select(Coupon).where(Coupon.status == 1).order_by(Coupon.create_time.desc())
    )).scalars().all()
    grabbed_ids = set((await db.execute(
        select(UserCoupon.coupon_id).where(UserCoupon.user_id == user_id)
    )).scalars().all())
    now = datetime.now()
    result = []
    for c in coupons:
        stock = await _real_stock(c.id, c.stock, c.end_time)
        vo = _coupon_vo(c, stock)
        if c.id in grabbed_ids:
            vo["grabStatus"] = "grabbed"  # 已领取
        elif now < c.start_time:
            vo["grabStatus"] = "not_started"  # 未开始
        elif now > c.end_time:
            vo["grabStatus"] = "ended"  # 已结束
        elif stock <= 0:
            vo["grabStatus"] = "sold_out"  # 已抢完
        else:
            vo["grabStatus"] = "available"  # 可领取
        result.append(vo)
    return result


async def grab(db: AsyncSession, user_id: int, coupon_id: int) -> dict:
    """抢券:三层防超发(限领 SETNX → Lua 原子扣减 → MySQL 唯一约束兜底)"""
    now = datetime.now()
    # ① 活动校验(服务端时间,防前端绕过)
    coupon = await db.get(Coupon, coupon_id)
    if coupon is None or coupon.status != 1:
        raise BizException("优惠券不存在或已停用")
    if now < coupon.start_time:
        raise BizException("活动未开始")
    if now > coupon.end_time:
        raise BizException("活动已结束")
    if coupon.stock <= 0:
        raise BizException("手慢了,优惠券已抢完")

    # ② 一人限领(SETNX 原子;Redis 异常降级放行,由 DB 唯一约束兜底)
    limit_key = f"{COUPON_USER_PREFIX}{coupon_id}:{user_id}"
    ttl = max(int((coupon.end_time - now).total_seconds()), 60)
    try:
        claimed = await redis_setnx(limit_key, "1", ttl)
        if not claimed:
            raise BizException("您已领取过该优惠券")
    except BizException:
        raise
    except Exception as e:
        logger.warning("优惠券限领标记降级(DB唯一约束兜底): %s", e)

    # ③ Lua 原子扣减(Redis 闸门);失败回滚限领标记,可再次尝试
    deduct = await redis_stock_deduct(f"{COUPON_STOCK_PREFIX}{coupon_id}", 1)
    if deduct == -1:
        try:
            await redis_delete(limit_key)
        except Exception:
            pass
        raise BizException("手慢了,优惠券已抢完")

    # ④ 落库(同一事务):插入持有记录(含过期时间=领取时间+有效天数)+ 条件扣库存;唯一约束兜底并发
    try:
        expire_time = now + timedelta(days=coupon.valid_days)
        db.add(UserCoupon(user_id=user_id, coupon_id=coupon_id, status=0, expire_time=expire_time))
        r = await db.execute(
            text("UPDATE coupon SET stock = stock - 1 WHERE id = :id AND stock > 0"),
            {"id": coupon_id},
        )
        if r.rowcount != 1:
            await db.rollback()
            await _redis_incr_stock(f"{COUPON_STOCK_PREFIX}{coupon_id}", 1)  # 回补 Redis
            try:
                await redis_delete(limit_key)
            except Exception:
                pass
            raise BizException("手慢了,优惠券已抢完")
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # 唯一约束兜底:并发重复领取
        await _redis_incr_stock(f"{COUPON_STOCK_PREFIX}{coupon_id}", 1)
        try:
            await redis_delete(limit_key)
        except Exception:
            pass
        raise BizException("您已领取过该优惠券")

    coupon.stock -= 1
    return _coupon_vo(coupon, coupon.stock)


async def my_coupons(db: AsyncSession, user_id: int, status: Optional[int]) -> list:
    """我的券:按状态过滤;未用且已过期的展示为已过期(2)"""
    conds = [UserCoupon.user_id == user_id]
    if status is not None:
        conds.append(UserCoupon.status == status)
    rows = (await db.execute(
        select(UserCoupon).where(*conds).order_by(UserCoupon.create_time.desc())
    )).scalars().all()
    now = datetime.now()
    result = []
    for uc in rows:
        coupon = await db.get(Coupon, uc.coupon_id)
        if coupon is None:
            continue
        eff_status = uc.status
        if eff_status == 0 and uc.expire_time is not None and uc.expire_time < now:
            eff_status = 2  # 展示层计算过期(以领取时的过期时间为准)
        result.append({
            "id": uc.id,
            "couponId": uc.coupon_id,
            "name": coupon.name,
            "type": coupon.type,
            "amount": str(coupon.amount),
            "minAmount": str(coupon.min_amount),
            "status": eff_status,
            "expireTime": uc.expire_time,
            "createTime": uc.create_time,
            "useTime": uc.use_time,
            "orderId": uc.order_id,
        })
    return result
