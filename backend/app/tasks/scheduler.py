"""定时任务(与原项目 ShopTask 一致):
- 每分钟:下单超过15分钟未支付(status=1)的订单自动取消
- 每天凌晨1点:派送中超过1小时(status=4)的订单自动完成

多 worker / 多副本部署:
    每个 worker 都会启动一份 scheduler(APScheduler 是进程内的),因此任务执行前
    先抢 Redis 分布式锁(lock:task:{name}),保证同一时刻只有一个 worker 真正执行。
    锁 TTL 略大于执行间隔,持锁者崩溃后锁自动过期,下一轮由其他 worker 接管。
    Redis 不可用时降级为本进程执行(不阻塞业务;单 worker 场景不受影响)。
"""
import logging
import uuid
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Orders
from app.services.order_service import _restore_stock

logger = logging.getLogger("uvicorn.error")


async def _run_with_lock(task_name: str, lock_ttl: int, coro):
    """抢到锁才执行任务(多副本防重复);Redis 不可用则降级执行。"""
    lock_key, lock_id = f"lock:task:{task_name}", uuid.uuid4().hex
    acquired = False
    try:
        from app.core.redis import redis_setnx

        acquired = await redis_setnx(lock_key, lock_id, lock_ttl)
        if not acquired:
            logger.debug("定时任务 %s 由其他 worker 执行,跳过", task_name)
            return
    except Exception as e:
        logger.warning("定时任务锁降级(Redis不可用,本进程执行 %s): %s", task_name, e)

    try:
        await coro()
    finally:
        if acquired:
            try:
                from app.core.redis import redis_release_lock

                await redis_release_lock(lock_key, lock_id)
            except Exception:
                pass


async def deal_with_timeout_order():
    """每60秒执行:查询超时未支付的订单并取消(回补库存,幂等)"""
    await _run_with_lock("timeout_order_cancel", 55, _do_deal_with_timeout_order)


async def _do_deal_with_timeout_order():
    async with AsyncSessionLocal() as db:
        try:
            deadline = datetime.now() - timedelta(minutes=15)
            rows = list((await db.execute(
                select(Orders).where(Orders.order_time <= deadline, Orders.status == 1)
            )).scalars().all())
            for order in rows:
                order.status = 6
                order.cancel_time = datetime.now()
                order.cancel_reason = "支付超时，取消订单"
                await _restore_stock(db, order)  # 超时取消回补库存(幂等,防与用户取消双回补)
            await db.commit()
            if rows:
                logger.info(f"定时任务: 自动取消 {len(rows)} 个超时订单")
        except Exception as e:
            logger.exception(f"定时任务超时取消失败: {e}")
            await db.rollback()


async def check_delivering_orders():
    """每天凌晨1点:派送中超过1小时的订单自动完成"""
    await _run_with_lock("delivering_order_complete", 300, _do_check_delivering_orders)


async def _do_check_delivering_orders():
    async with AsyncSessionLocal() as db:
        try:
            deadline = datetime.now() - timedelta(hours=1)
            rows = list((await db.execute(
                select(Orders).where(Orders.order_time <= deadline, Orders.status == 4)
            )).scalars().all())
            for order in rows:
                order.status = 5
                order.delivery_time = datetime.now()
            await db.commit()
            if rows:
                logger.info(f"定时任务: 自动完成 {len(rows)} 个派送中订单")
        except Exception as e:
            logger.exception(f"定时任务自动完成失败: {e}")
            await db.rollback()


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    # 每分钟的第0秒执行
    scheduler.add_job(
        deal_with_timeout_order,
        CronTrigger(minute="*", second="0"),
        id="timeout_order_cancel",
    )
    # 每天凌晨1点
    scheduler.add_job(
        check_delivering_orders,
        CronTrigger(hour=1, minute=0),
        id="delivering_order_complete",
    )
    return scheduler
