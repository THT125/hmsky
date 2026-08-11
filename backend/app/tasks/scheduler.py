"""定时任务(与原项目 ShopTask 一致):
- 每分钟:下单超过15分钟未支付(status=1)的订单自动取消
- 每天凌晨1点:派送中超过1小时(status=4)的订单自动完成
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Orders

logger = logging.getLogger("uvicorn.error")


async def deal_with_timeout_order():
    """每60秒执行:查询超时未支付的订单并取消"""
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
            await db.commit()
            if rows:
                logger.info(f"定时任务: 自动取消 {len(rows)} 个超时订单")
        except Exception as e:
            logger.exception(f"定时任务超时取消失败: {e}")
            await db.rollback()


async def check_delivering_orders():
    """每天凌晨1点:派送中超过1小时的订单自动完成"""
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
