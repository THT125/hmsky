"""热销排行榜:MySQL 权威 + Redis ZSet 加速。
- 销量 = 已支付订单明细聚合(MySQL 权威,重启自愈)
- ZSet:hot:dishes / hot:setmeals,member=商品id,score=销量(支付 ZINCRBY,退款 ZDECRBY)
- 榜单读取:懒回填(空/miss 时从 DB 重建,TTL 1 小时定期与 DB 收敛)
- 重建用分布式锁防重复聚合(抢锁者执行回填,其余等待后读缓存)
"""
import asyncio
import logging
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    HOT_DISHES_KEY,
    HOT_SETMEALS_KEY,
    redis_expire,
    redis_release_lock,
    redis_setnx,
    redis_zadd,
    redis_zrevrange_withscores,
)
from app.models import Dish, Setmeal

logger = logging.getLogger("uvicorn.error")

HOT_TTL = 3600  # 排行榜缓存 1 小时过期重建(与 DB 收敛,防长期漂移)
TOP_DEFAULT = 10     # 默认 TOP 10
_REBUILD_LOCK_TTL = 5  # 重建锁超时(秒):回填需在此时间内完成,防死锁
_REBUILD_WAIT_ROUNDS = 5  # 未抢到锁的最大等待轮数(每轮 0.1s)


async def _backfill(db: AsyncSession, key: str, kind: int) -> None:
    """从 MySQL 聚合已支付订单的销量,回填 ZSet(带 TTL)"""
    if kind == 1:
        sql = text("""
            SELECT od.dish_id AS id, SUM(od.number) AS sold
            FROM order_detail od JOIN orders o ON od.order_id = o.id
            WHERE od.dish_id IS NOT NULL AND o.pay_status = 1
            GROUP BY od.dish_id
        """)
    else:
        sql = text("""
            SELECT od.setmeal_id AS id, SUM(od.number) AS sold
            FROM order_detail od JOIN orders o ON od.order_id = o.id
            WHERE od.setmeal_id IS NOT NULL AND o.pay_status = 1
            GROUP BY od.setmeal_id
        """)
    rows = (await db.execute(sql)).all()
    mapping = {int(r.id): int(r.sold) for r in rows if r.id is not None}
    try:
        if mapping:
            await redis_zadd(key, mapping)
        await redis_expire(key, HOT_TTL)
    except Exception as e:
        logger.warning("热销榜回填降级: %s", e)


async def _read_rank(key: str, top: int) -> list:
    """读排行榜 TOP N,Redis 异常降级返回空(触发重建)"""
    try:
        return await redis_zrevrange_withscores(key, 0, top - 1)
    except Exception as e:
        logger.warning("读热销榜降级(查DB重建): %s", e)
        return []


async def list_hot(db: AsyncSession, kind: int, top: int = TOP_DEFAULT) -> list:
    """热销排行榜:先读 ZSet,空/miss 时分布式锁防重复重建"""
    top = min(max(top, 1), 50)            # 把传入的 `top` 参数强制限制在 `[1, 50]` 之间
    key = HOT_DISHES_KEY if kind == 1 else HOT_SETMEALS_KEY

    rows = await _read_rank(key, top)
    if rows:
        return await _build_list(db, kind, rows)

    # miss → 分布式锁:抢到者执行回填,其余等待后重读(防多人重复聚合 MySQL)
    lock_key, lock_id = f"lock:{key}", uuid.uuid4().hex
    got_lock = False
    try:
        got_lock = await redis_setnx(lock_key, lock_id, _REBUILD_LOCK_TTL)
        if got_lock:
            await _backfill(db, key, kind)
            rows = await _read_rank(key, top)
        else:
            for _ in range(_REBUILD_WAIT_ROUNDS):
                await asyncio.sleep(0.1)  # 等待持锁者重建
                rows = await _read_rank(key, top)
                if rows:
                    break
    finally:
        if got_lock:
            await redis_release_lock(lock_key, lock_id)  # 安全释放(校验 value)

    if not rows:  # 兜底:等待超时(持锁者异常)直接回填
        await _backfill(db, key, kind)
        rows = await _read_rank(key, top)
    return await _build_list(db, kind, rows)


async def _build_list(db: AsyncSession, kind: int, rows: list) -> list:
    result = []
    for rank, (member, score) in enumerate(rows, start=1):
        item = await _build_item(db, kind, int(member), int(score))
        if item:
            item["rank"] = rank
            result.append(item)
    return result


async def _build_item(db: AsyncSession, kind: int, item_id: int, sold: int) -> Optional[dict]:
    if kind == 1:
        dish = await db.get(Dish, item_id)
        if dish is None:
            return None
        return {"id": dish.id, "name": dish.name, "price": str(dish.price) if dish.price else None,
                "image": dish.image, "description": dish.description, "sold": sold}
    setmeal = await db.get(Setmeal, item_id)
    if setmeal is None:
        return None
    return {"id": setmeal.id, "name": setmeal.name, "price": str(setmeal.price) if setmeal.price else None,
            "image": setmeal.image, "description": setmeal.description, "sold": sold}
