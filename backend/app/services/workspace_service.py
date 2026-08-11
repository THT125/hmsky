"""工作台统计(口径与原 OrderMapper.xml 一致:
- 营业额按 DATE(checkout_time)=今天 且 status=5
- 完成率 = 有效订单 / 今日全部订单(按 checkout_time),2位小数,除零返回0
- 客单价 = 营业额 / 有效订单数
- 订单概览按 DATE(order_time)=今天 统计 status 2/3/5/6 与全部
- 菜品/套餐概览为全库 status 计数
"""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Dish, Orders, Setmeal, User


def _today() -> date:
    return datetime.now().date()


async def business_data(db: AsyncSession) -> dict:
    today = _today()
    base = await db.scalar(
        select(func.coalesce(func.sum(Orders.amount), 0)).where(
            func.date(Orders.checkout_time) == today, Orders.status == 5
        )
    )
    turnover = Decimal(str(base or 0))
    valid_order_count = await db.scalar(
        select(func.count(Orders.id)).where(
            func.date(Orders.checkout_time) == today, Orders.status == 5
        )
    ) or 0
    all_order_count = await db.scalar(
        select(func.count(Orders.id)).where(func.date(Orders.checkout_time) == today)
    ) or 0
    new_users = await db.scalar(
        select(func.count(User.id)).where(func.date(User.create_time) == today)
    ) or 0

    completion_rate = (
        (Decimal(valid_order_count) / Decimal(all_order_count))
        .quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        if all_order_count else Decimal("0.00")
    )
    unit_price = (
        (turnover / Decimal(valid_order_count))
        .quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        if valid_order_count else Decimal("0.00")
    )
    return {
        "turnover": float(turnover),
        "validOrderCount": valid_order_count,
        "orderCompletionRate": float(completion_rate),
        "unitPrice": float(unit_price),
        "newUsers": new_users,
    }


async def overview_orders(db: AsyncSession) -> dict:
    today = _today()

    async def cnt(status=None):
        conds = [func.date(Orders.order_time) == today]
        if status is not None:
            conds.append(Orders.status == status)
        return await db.scalar(select(func.count(Orders.id)).where(*conds)) or 0

    return {
        "allOrders": await cnt(),
        "waitingOrders": await cnt(2),
        "deliveredOrders": await cnt(3),
        "completedOrders": await cnt(5),
        "cancelledOrders": await cnt(6),
    }


async def overview_dishes(db: AsyncSession) -> dict:
    return {
        "sold": await db.scalar(select(func.count(Dish.id)).where(Dish.status == 1)) or 0,
        "discontinued": await db.scalar(select(func.count(Dish.id)).where(Dish.status == 0)) or 0,
    }


async def overview_setmeals(db: AsyncSession) -> dict:
    return {
        "sold": await db.scalar(select(func.count(Setmeal.id)).where(Setmeal.status == 1)) or 0,
        "discontinued": await db.scalar(select(func.count(Setmeal.id)).where(Setmeal.status == 0)) or 0,
    }
